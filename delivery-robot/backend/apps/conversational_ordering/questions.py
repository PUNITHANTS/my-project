"""Tap-to-answer options for repair and clarification questions.

Every option is taken from the validator's output or from settings, so a chip the
kiosk shows is always a value the backend will accept. Slots:

- ``item:<line>``     pick the menu item for a line        -> ``menuItemId``
- ``option:<line>``   pick a customization for a line      -> ``value``
- ``quantity:<line>`` set a line's quantity                -> ``value``
- ``location``        pick the delivery location           -> ``value``
- ``vendor``          keep only one vendor's lines         -> ``value``
"""

from django.conf import settings

from .menu_validation import candidate_label


MAX_OPTIONS = 8
REMOVE_CUSTOMIZATION = ""


def _item_options(line, candidates):
    shown = candidates[:MAX_OPTIONS]
    return [
        {
            "slot": f"item:{line}",
            "label": candidate_label(candidate, shown),
            "menuItemId": str(candidate["menu_item_id"]),
        }
        for candidate in shown
    ]


def _customization_options(line, choices):
    return [
        {"slot": f"option:{line}", "label": choice, "value": choice}
        for choice in choices[:MAX_OPTIONS]
    ]


def _vendor_options(parsed, catalog):
    by_id = {item["id"]: item for item in catalog}
    vendors = {}
    for line in parsed.items:
        menu_item = by_id.get(str(line.menu_item_id))
        if menu_item:
            vendors.setdefault(menu_item["vendor_id"], menu_item["vendor"])
    return [
        {"slot": "vendor", "label": name, "value": str(vendor_id)}
        for vendor_id, name in vendors.items()
    ]


def repair_options(validation, parsed, catalog):
    """Options for the first violation, the one the repair question asks about."""
    if not validation["violations"]:
        return []
    violation = validation["violations"][0]
    code = violation["code"]
    line = violation.get("line")
    if code == "missing_location":
        return [
            {"slot": "location", "label": location, "value": location}
            for location in settings.AI_DELIVERY_LOCATIONS[:MAX_OPTIONS]
        ]
    if code == "multiple_vendors":
        return _vendor_options(parsed, catalog)
    if code in ("unknown_item", "unavailable_item"):
        return _item_options(line, violation.get("alternatives") or [])
    if code == "invalid_customization":
        return _customization_options(line, violation.get("alternatives") or []) + [
            {
                "slot": f"option:{line}",
                "label": "Leave it out",
                "value": REMOVE_CUSTOMIZATION,
            }
        ]
    if code == "too_many_customizations":
        return _customization_options(line, violation.get("alternatives") or [])
    if code == "quantity_limit":
        maximum = violation["max_quantity"]
        return [
            {
                "slot": f"quantity:{line}",
                "label": f"Make it {maximum}",
                "value": str(maximum),
            }
        ]
    return []


def clarification_options(validation):
    """Options for the detail the clarification question asks about."""
    if validation["missing_details"]:
        detail = validation["missing_details"][0]
        return _customization_options(detail["line"], detail["choices"])
    ambiguous = next(
        (match for match in validation["near_matches"] if match["count"] >= 2), None
    )
    if ambiguous:
        return _item_options(ambiguous["line"], ambiguous["candidates"])
    return []


def question_line(action, validation):
    """The cart line a REPAIR or ASK question is about, or None for the whole order.

    Mirrors the order in which the question builders pick what to ask.
    """
    if action == "REPAIR":
        violations = validation["violations"]
        return violations[0].get("line") if violations else None
    if validation["missing_details"]:
        return validation["missing_details"][0]["line"]
    ambiguous = next(
        (match for match in validation["near_matches"] if match["count"] >= 2), None
    )
    return ambiguous["line"] if ambiguous else None
