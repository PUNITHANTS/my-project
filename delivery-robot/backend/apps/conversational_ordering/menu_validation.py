import re
from difflib import SequenceMatcher

from django.utils import timezone

from apps.menu.models import MenuItem
from apps.vendors.models import Vendor


STOP_WORDS = {"a", "an", "the", "of", "and", "with", "please", "some"}
# Words that say how many, not which item: "two pizzas" should match pizzas.
COUNT_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "order", "orders", "couple", "few",
}


def normalize_text(value):
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def item_is_available(item, now=None):
    now = timezone.localtime(now or timezone.now())
    if not item.is_available or not item.vendor.is_active or item.vendor.intake_paused:
        return False

    windows = [window for window in item.availability_windows.all() if window.is_active]
    if not windows:
        return True
    return any(
        window.weekday == now.weekday()
        and window.start_time <= now.time().replace(tzinfo=None) < window.end_time
        for window in windows
    )


def load_menu_catalog():
    now = timezone.localtime()
    items = (
        MenuItem.objects.select_related("vendor")
        .prefetch_related("option_groups__options", "availability_windows")
        .order_by("vendor__name", "name")
    )
    catalog = []
    for item in items:
        option_groups = []
        for group in item.option_groups.all():
            option_groups.append(
                {
                    "id": group.id,
                    "name": group.name,
                    "required": group.is_required or group.min_selections > 0,
                    "min_selections": group.min_selections,
                    "max_selections": group.max_selections,
                    "options": [
                        option.name
                        for option in group.options.all()
                        if option.is_available
                    ],
                }
            )
        catalog.append(
            {
                "id": str(item.pk),
                "name": item.name,
                "description": item.description,
                "price": str(item.price),
                "vendor_id": item.vendor_id,
                "vendor": item.vendor.name,
                "vendor_location": item.vendor.location_label,
                "available": item_is_available(item, now),
                "max_quantity": item.max_quantity,
                "option_groups": option_groups,
            }
        )
    return catalog


def _singular(word):
    if len(word) <= 3 or word.endswith("ss"):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("es") and word[:-2].endswith(("ch", "sh", "x")):
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def match_tokens(value):
    """Content words of ``value``, singular, for comparing mentions with item names."""
    words = normalize_text(value).split()
    return {_singular(word) for word in words if not word.isdigit()} - STOP_WORDS - COUNT_WORDS


def names_item(text, item_name):
    """True when ``text`` contains every content word of the item's name.

    "two grilled chicken burgers" names Grilled Chicken Burger; "a burger" names
    no item, because several items share the word.
    """
    name_words = match_tokens(item_name)
    return bool(name_words) and name_words <= match_tokens(text)


def _match_score(mention, item_name):
    left = match_tokens(mention)
    right = match_tokens(item_name)
    if not left or not right:
        return 0.0
    if left.issubset(right) or right.issubset(left):
        return 1.0
    overlap = len(left & right) / len(left | right)
    sequence = SequenceMatcher(None, " ".join(sorted(left)), " ".join(sorted(right))).ratio()
    return max(overlap, sequence)


def _candidate_items(mention, catalog, threshold):
    available = [item for item in catalog if item["available"]]
    # A mention that spells out an item's full name is not ambiguous, even when
    # other names share some of its words. If several full names fit ("veggie
    # burger" also contains "burger"), the longest, most specific one wins.
    named = [item for item in available if names_item(mention, item["name"])]
    if named:
        longest = max(len(match_tokens(item["name"])) for item in named)
        return [
            {"menu_item_id": item["id"], "name": item["name"], "score": 1.0}
            for item in named
            if len(match_tokens(item["name"])) == longest
        ]
    ranked = [(item, _match_score(mention, item["name"])) for item in available]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return [
        {"menu_item_id": item["id"], "name": item["name"], "score": round(score, 4)}
        for item, score in ranked
        if score >= threshold
    ]


def validate_draft(parsed, catalog, near_match_threshold, resolved_item_ids=()):
    """Check a draft against the menu.

    ``resolved_item_ids`` are menu items the customer picked by tapping an option;
    a line holding one of them is no longer treated as an ambiguous mention.
    Every per-line entry carries ``line``, the line's position in the draft.
    """
    resolved = {str(value) for value in resolved_item_ids}
    by_id = {item["id"]: item for item in catalog}
    violations = []
    missing_details = []
    near_matches = []
    vendor_ids = set()

    if not parsed.items:
        violations.append({"code": "empty_order", "message": "Add at least one menu item."})
    if not (parsed.delivery_location or "").strip():
        violations.append(
            {"code": "missing_location", "message": "A delivery location is required."}
        )

    for index, line in enumerate(parsed.items):
        menu_item = by_id.get(str(line.menu_item_id)) if line.menu_item_id else None
        candidates = _candidate_items(line.mention, catalog, near_match_threshold)
        if menu_item is not None and menu_item["id"] in resolved:
            candidates = [
                {"menu_item_id": menu_item["id"], "name": menu_item["name"], "score": 1.0}
            ]
        elif (
            menu_item is not None
            and not candidates
            and not (match_tokens(line.mention) & match_tokens(menu_item["name"]))
        ):
            # The model mapped a general word ("two drinks") to an item whose name
            # shares nothing with it. That choice is a guess, so treat the line as
            # ambiguous among the same vendor's items instead of trusting it.
            candidates = [
                {"menu_item_id": item["id"], "name": item["name"], "score": 0.0}
                for item in catalog
                if item["available"] and item["vendor_id"] == menu_item["vendor_id"]
            ]
        near_matches.append(
            {
                "line": index,
                "mention": line.mention,
                "count": len(candidates),
                "candidates": candidates,
            }
        )
        if menu_item is None:
            violations.append(
                {
                    "code": "unknown_item",
                    "line": index,
                    "item_id": line.menu_item_id,
                    "message": f"'{line.mention}' does not identify a current menu item.",
                    "alternatives": candidates[:5],
                }
            )
            continue

        vendor_ids.add(menu_item["vendor_id"])
        if not menu_item["available"]:
            alternatives = [item for item in catalog if item["available"]]
            violations.append(
                {
                    "code": "unavailable_item",
                    "line": index,
                    "item_id": menu_item["id"],
                    "message": f"{menu_item['name']} is currently unavailable.",
                    "alternatives": _candidate_items(
                        line.mention, alternatives, near_match_threshold
                    )[:5],
                }
            )
        if line.quantity > menu_item["max_quantity"]:
            violations.append(
                {
                    "code": "quantity_limit",
                    "line": index,
                    "max_quantity": menu_item["max_quantity"],
                    "item_id": menu_item["id"],
                    "message": f"The maximum quantity for {menu_item['name']} is {menu_item['max_quantity']}.",
                }
            )

        selected = {normalize_text(value) for value in line.customizations}
        all_offered = {
            normalize_text(option)
            for group in menu_item["option_groups"]
            for option in group["options"]
        }
        invalid_options = selected - all_offered
        if invalid_options:
            offered = [
                option
                for group in menu_item["option_groups"]
                for option in group["options"]
            ]
            violations.append(
                {
                    "code": "invalid_customization",
                    "line": index,
                    "item_id": menu_item["id"],
                    "message": f"Choose customizations offered for {menu_item['name']}.",
                    "alternatives": offered,
                }
            )
        for group in menu_item["option_groups"]:
            options = {normalize_text(value) for value in group["options"]}
            selected_in_group = selected & options
            min_required = max(1 if group["required"] else 0, group["min_selections"])
            if len(selected_in_group) > group["max_selections"]:
                violations.append(
                    {
                        "code": "too_many_customizations",
                        "line": index,
                        "item_id": menu_item["id"],
                        "message": f"Choose at most {group['max_selections']} option(s) for {group['name']}.",
                        "alternatives": group["options"],
                    }
                )
            if group["required"] and len(selected_in_group) < min_required:
                missing_details.append(
                    {
                        "kind": "required_option",
                        "line": index,
                        "item_id": menu_item["id"],
                        "item_name": menu_item["name"],
                        "group": group["name"],
                        "choices": group["options"],
                    }
                )

    if len(vendor_ids) > 1:
        violations.append(
            {"code": "multiple_vendors", "message": "An order must contain items from one vendor."}
        )
    return {
        "valid": not violations,
        "violations": violations,
        "missing_details": missing_details,
        "near_matches": near_matches,
        "vendor_id": next(iter(vendor_ids)) if len(vendor_ids) == 1 else None,
    }


def validate_order_submission(vendor_id, delivery_location, items):
    errors = []
    try:
        vendor = Vendor.objects.get(pk=vendor_id)
    except Vendor.DoesNotExist:
        return ["The selected vendor does not exist."]
    if not vendor.is_active or vendor.intake_paused:
        errors.append("This vendor is not accepting orders right now.")
    if not delivery_location.strip():
        errors.append("A delivery location is required.")
    if not items:
        errors.append("An order must contain at least one item.")

    for row in items:
        try:
            item = (
                MenuItem.objects.select_related("vendor")
                .prefetch_related("option_groups__options", "availability_windows")
                .get(pk=row["menu_item_id"])
            )
        except MenuItem.DoesNotExist:
            errors.append("An order item is not on the menu.")
            continue
        if item.vendor_id != vendor.pk:
            errors.append("All order items must belong to the selected vendor.")
        if not item_is_available(item):
            errors.append(f"{item.name} is currently unavailable.")
        if row["quantity"] > item.max_quantity:
            errors.append(f"The maximum quantity for {item.name} is {item.max_quantity}.")

        selected = {
            normalize_text(value)
            for value in (row.get("customization") or "").split(",")
            if value.strip()
        }
        groups = list(item.option_groups.all())
        offered = {
            normalize_text(option.name)
            for group in groups
            for option in group.options.all()
            if option.is_available
        }
        if selected - offered:
            errors.append(f"A customization is not offered for {item.name}.")
        for group in groups:
            group_options = {
                normalize_text(option.name)
                for option in group.options.all()
                if option.is_available
            }
            selected_count = len(selected & group_options)
            min_required = max(
                1 if group.is_required or group.min_selections > 0 else 0,
                group.min_selections,
            )
            if selected_count > group.max_selections:
                errors.append(f"Choose at most {group.max_selections} option(s) for {group.name}.")
            if selected_count < min_required:
                errors.append(f"Choose an option for {group.name} on {item.name}.")
    return errors
