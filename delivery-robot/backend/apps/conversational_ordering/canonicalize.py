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
"""

import re

from .menu_validation import normalize_text
from .schemas import ParsedOrder


def _phrase_in(text, phrase):
    return bool(phrase) and re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _canonical_option(value, menu_item):
    """Return the menu's spelling of ``value`` or None if it names no option."""
    wanted = normalize_text(value)
    if not wanted:
        return None
    for group in menu_item["option_groups"]:
        for option in group["options"]:
            if normalize_text(option) == wanted:
                return option
    for group in menu_item["option_groups"]:
        prefix = normalize_text(group["name"])
        if wanted.startswith(prefix + " "):
            rest = wanted[len(prefix) + 1:].strip()
            for option in group["options"]:
                if normalize_text(option) == rest:
                    return option
    return None


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


def canonicalize_draft(parsed, transcript, catalog, previous=None):
    """Return ``(parsed, notes)`` with the rules above applied."""
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

    if not notes:
        return parsed, []
    return ParsedOrder.model_validate(data), notes
