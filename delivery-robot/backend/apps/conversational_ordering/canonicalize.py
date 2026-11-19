"""Deterministic clean-up of the model's draft before validation.

The model gets the order right but writes it in shapes the validator rejects or
that differ from what the customer said. Each rule here fixes one such shape
seen in the C1-C5 traces, using only the menu and the customer's own words:

* ``"Size: Regular"`` / ``"Sauce Teriyaki"``: the group name is copied in front
  of the option. Mapped to the menu's option name.
* A required option the customer said this turn ("two regular colas", "on
  white") is left out. Filled when exactly one option of that group is named,
  in the line's own mention or, for a one-item draft, anywhere in the turn.
* "Make that two" drops a size chosen earlier. The earlier choice is kept when
  the model leaves that group empty for the same item.
* "Two X, one of them with Y" comes back as a line of two plus a line of one.
  The plain line is reduced by one.
* ``"Toppings: Black olives"`` / ``"Size (required): Large"`` / ``"Onion"``: any
  prefix ending in a colon is dropped, and an option is matched ignoring a
  plural "s" or a leading describing word, when exactly one option fits.
* ``"No sausage"`` / ``"Hold tuna"`` where sausage or tuna is an add-on of the
  item: the customer asked for it not to be added, which is the default, so
  the value is dropped.
* The model leaves the location empty although the turn names exactly one
  known delivery location ("Can Calcia Hall get a lamb curry?"). It is filled.
"""

import re

from django.conf import settings

from .menu_validation import normalize_text
from .schemas import ParsedOrder


def _phrase_in(text, phrase):
    return bool(phrase) and re.search(rf"\b{re.escape(phrase)}\b", text) is not None


NEGATION = re.compile(r"^(no|without|hold|hold the|minus|skip)\s+\S")


def _singular(text):
    return " ".join(word[:-1] if len(word) > 3 and word.endswith("s") else word for word in text.split())


def _exact_option(wanted, menu_item):
    for group in menu_item["option_groups"]:
        for option in group["options"]:
            if normalize_text(option) == wanted:
                return option
    return None


def _canonical_option(value, menu_item):
    """Return the menu's spelling of ``value`` or None if it names no option."""
    wanted = normalize_text(value)
    if not wanted:
        return None
    exact = _exact_option(wanted, menu_item)
    if exact is not None:
        return exact
    candidates = []
    if ":" in value:
        candidates.append(normalize_text(value.rsplit(":", 1)[1]))
    for group in menu_item["option_groups"]:
        prefix = normalize_text(group["name"])
        if wanted.startswith(prefix + " "):
            candidates.append(wanted[len(prefix) + 1:].strip())
    for rest in candidates:
        exact = _exact_option(rest, menu_item)
        if exact is not None:
            return exact
    # "Onion" for "Onions", "Black olives" for "Olives": accept only a unique fit.
    # Never for a negation: "No ham" must not become "Ham".
    for rest in candidates or [wanted]:
        if NEGATION.match(rest):
            continue
        target = _singular(rest)
        fits = {
            option
            for group in menu_item["option_groups"]
            for option in group["options"]
            if _singular(normalize_text(option)) == target
            or target.endswith(" " + _singular(normalize_text(option)))
        }
        if len(fits) == 1:
            return fits.pop()
    return None


def _named_locations(text, locations):
    found = [loc for loc in locations if _phrase_in(text, normalize_text(loc))]
    return [
        loc for loc in found
        if not any(other != loc and _phrase_in(normalize_text(other), normalize_text(loc)) for other in found)
    ]


def _named_options(text, group):
    """Options of ``group`` that appear in ``text``, ignoring ones contained in a longer match."""
    found = [option for option in group["options"] if _phrase_in(text, normalize_text(option))]
    return [
        option
        for option in found
        if not any(
            other != option and _phrase_in(normalize_text(other), normalize_text(option))
            for other in found
        )
    ]


def canonicalize_draft(parsed, transcript, catalog, previous=None, locations=None):
    """Return ``(parsed, notes)`` with the rules above applied.

    ``locations`` defaults to ``settings.AI_DELIVERY_LOCATIONS``.
    """
    by_id = {item["id"]: item for item in catalog}
    data = parsed.model_dump(mode="json")
    text = normalize_text(transcript)
    notes = []
    previous_lines = (previous or {}).get("items", [])
    single_item = len({str(line.get("menu_item_id")) for line in data["items"]}) == 1

    for index, line in enumerate(data["items"]):
        menu_item = by_id.get(str(line.get("menu_item_id")))
        if menu_item is None:
            continue
        cleaned = []
        for value in line.get("customizations") or []:
            if not normalize_text(value):
                notes.append({"line": index, "action": "dropped_empty_customization"})
                continue
            canonical = _canonical_option(value, menu_item)
            negated = NEGATION.match(normalize_text(value))
            if canonical is None and negated:
                # "No sausage" where sausage is an add-on of this item: leaving
                # it unselected is what the customer asked for. A negation the
                # menu does not model ("no mayo" on a burger without a mayo
                # option) is left for the validator to ask about.
                rest = normalize_text(value)[negated.end(1):].strip()
                add_on = _canonical_option(rest, menu_item)
                if add_on is not None and normalize_text(add_on) not in {
                    normalize_text(v) for v in line.get("customizations") or [] if v != value
                }:
                    notes.append({"line": index, "action": "dropped_negated_option", "from": value})
                    continue
            if canonical is not None and canonical != value:
                notes.append({"line": index, "action": "canonical_option", "from": value, "to": canonical})
            cleaned.append(canonical if canonical is not None else value)
        line["customizations"] = cleaned

        selected = {normalize_text(value) for value in cleaned}
        for group in menu_item["option_groups"]:
            if not group["required"] or group["max_selections"] != 1:
                continue
            if selected & {normalize_text(option) for option in group["options"]}:
                continue
            # Prefer the line's own wording; the whole turn is only safe when the
            # draft holds one item ("a large coffee and a small pizza" must not
            # give the pizza "Large").
            named = _named_options(normalize_text(line.get("mention") or ""), group)
            if not named and single_item:
                named = _named_options(text, group)
            if len(named) == 1:
                line["customizations"].append(named[0])
                notes.append({"line": index, "action": "filled_named_option", "option": named[0]})
                continue
            if named:
                continue
            earlier = {
                option
                for old in previous_lines
                if str(old.get("menu_item_id")) == menu_item["id"]
                for option in group["options"]
                if normalize_text(option) in {normalize_text(v) for v in old.get("customizations") or []}
            }
            if len(earlier) == 1:
                option = earlier.pop()
                line["customizations"].append(option)
                notes.append({"line": index, "action": "kept_earlier_option", "option": option})

    if re.search(r"\bone of them\b", text):
        for item_id in {str(line.get("menu_item_id")) for line in data["items"]}:
            lines = [line for line in data["items"] if str(line.get("menu_item_id")) == item_id]
            if len(lines) != 2:
                continue
            big, small = sorted(lines, key=lambda line: -line["quantity"])
            extra = set(map(normalize_text, small["customizations"])) - set(
                map(normalize_text, big["customizations"])
            )
            if small["quantity"] == 1 and big["quantity"] >= 2 and extra:
                big["quantity"] -= 1
                notes.append({"menu_item_id": item_id, "action": "split_one_of_them"})

    if not data.get("delivery_location"):
        named = _named_locations(text, settings.AI_DELIVERY_LOCATIONS if locations is None else locations)
        if len(named) == 1:
            data["delivery_location"] = named[0]
            notes.append({"slot": "delivery_location", "action": "filled_named_location", "to": named[0]})

    if not notes:
        return parsed, []
    return ParsedOrder.model_validate(data), notes
