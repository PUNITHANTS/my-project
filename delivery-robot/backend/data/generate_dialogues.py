"""Generate 1,000 annotated dialogues and a plain-English Word review copy.

The Word file is written beside android-kiosk, backend, and vendor-console.
The JSONL file is what the experiment runner reads.
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.shared import Pt

ROOT = Path(__file__).resolve().parents[2]
MENU_PATH = Path(__file__).resolve().parent / "menu_snapshot_v1.json"
JSONL_PATH = Path(__file__).resolve().parent / "dialogues.jsonl"
DOC_PATH = ROOT / "Annotated_Orders.docx"

LOCATIONS = [
    "Sprague Library",
    "Student Center",
    "University Hall",
    "Blanton Hall",
    "Recreation Center",
    "Dickson Hall",
    "Calcia Hall",
    "Freeman Hall",
    "Richardson Hall",
    "Partridge Hall",
    "Life Hall",
    "College Hall",
]

IRREGULAR = {"fries", "onion rings", "chicken tenders"}
VAGUE = {
    "101": "burger",
    "102": "burger",
    "103": "burger",
    "104": "burger",
    "105": "wrap",
    "301": "wrap",
    "201": "drink",
    "202": "drink",
    "203": "drink",
    "204": "drink",
    "208": "drink",
    "302": "sandwich",
    "304": "sandwich",
    "401": "pizza",
    "402": "pizza",
    "403": "pizza",
    "501": "smoothie",
    "502": "smoothie",
    "503": "rice bowl",
    "504": "rice bowl",
}
QTY_WORDS = {1: "one", 2: "two", 3: "three"}
INVALID_REQUESTS = [
    "a large lemonade",
    "a small lemonade",
    "an iced latte",
    "the seasonal soup",
    "a meatball sub",
    "an acai bowl",
    "a bagel with jam",
    "a pineapple pizza",
    "a diet cola",
    "small fries",
    "a wheat grilled cheese",
    "a coffee with almond milk",
    "a kids pizza",
    "a milkshake",
    "a caesar salad",
    "a fish sandwich",
    "an onion soup",
    "pancakes",
    "a breakfast burrito",
    "sweet tea",
    "a cappuccino",
    "mozzarella sticks",
    "a chicken quesadilla",
    "fries with cheese sauce",
    "chicken tenders with ketchup",
    "a garden salad with caesar dressing",
    "potato chips with nacho cheese",
    "a sprite",
    "a gluten-free pizza",
    "a wrap with bacon",
]


def load_menu():
    payload = json.loads(MENU_PATH.read_text(encoding="utf-8"))
    items = []
    for item in payload["items"]:
        if not item["available"]:
            continue
        items.append(item)
    return payload, items


def pluralize(name: str, n: int) -> str:
    if n == 1 or name in IRREGULAR:
        return name
    if name.endswith("sandwich"):
        return name + "es"
    if name.endswith("s"):
        return name
    return name + "s"


def article(phrase: str) -> str:
    return "an" if phrase[:1].lower() in "aeiou" else "a"


def selected_bits(selected):
    size = None
    flavor = None
    plain_spread = False
    extras = []
    for group_name, option in selected:
        if group_name == "Size":
            size = option.lower()
        elif group_name == "Flavor":
            flavor = option.lower()
        elif group_name == "Spread" and option.lower() == "plain":
            plain_spread = True
        elif group_name == "Bread":
            extras.append(f"on {option.lower()}")
        else:
            extras.append(f"with {option.lower()}")
    return size, flavor, plain_spread, extras


def item_phrase(item, selected, n: int) -> str:
    spoken = item["name"].lower()
    size, flavor, plain_spread, extras = selected_bits(selected)
    if spoken == "potato chips":
        label = f"{flavor} potato chips" if flavor else "potato chips"
        phrase = f"a bag of {label}" if n == 1 else f"{QTY_WORDS[n]} bags of {label}"
    else:
        head = spoken
        if plain_spread:
            head = f"plain {head}"
        if size:
            head = f"{size} {head}"
        if spoken in IRREGULAR or "fries" in head or head.endswith("onion rings") or head.endswith("chicken tenders"):
            if n == 1:
                phrase = f"one order of {head}"
            else:
                phrase = f"{QTY_WORDS[n]} orders of {head}"
        else:
            word = pluralize(head, n)
            phrase = f"{article(word)} {word}" if n == 1 else f"{QTY_WORDS[n]} {word}"
    if extras:
        phrase = f"{phrase} {' and '.join(extras)}"
    return phrase


def required_choices(item):
    groups = []
    for group in item["option_groups"]:
        if group["required"]:
            groups.append([(group["name"], option) for option in group["options"]])
    if not groups:
        return [[]]
    combos = [[]]
    for group_choices in groups:
        combos = [current + [choice] for current in combos for choice in group_choices]
    return combos


def optional_singles(item):
    extras = [[]]
    for group in item["option_groups"]:
        if group["required"]:
            continue
        for option in group["options"]:
            extras.append([(group["name"], option)])
    return extras


def line(item, selected, n):
    return {
        "menu_item_id": item["id"],
        "quantity": n,
        "customizations": [option for _, option in selected],
    }


def gold_key(vendor_id, location, items):
    canon = tuple(
        sorted(
            (
                item["menu_item_id"],
                item["quantity"],
                tuple(sorted(item["customizations"])),
            )
            for item in items
        )
    )
    return (vendor_id, location, canon)


def english_gold(item_lookup, vendor_id, location, items, vendors):
    parts = []
    for entry in items:
        item = item_lookup[entry["menu_item_id"]]
        customs = entry["customizations"]
        detail = f" ({', '.join(customs)})" if customs else ""
        parts.append(f"{entry['quantity']} × {item['name']}{detail}")
    vendor = vendors[vendor_id]
    return f"{'; '.join(parts)}. {vendor}, deliver to {location}."


def take(pool, count, used):
    chosen = []
    for record in pool:
        if record["key"] in used:
            continue
        used.add(record["key"])
        chosen.append(record)
        if len(chosen) == count:
            break
    if len(chosen) < count:
        raise RuntimeError(f"Only found {len(chosen)} of {count} orders.")
    return chosen


def build_records(available):
    singles = []
    splits = []
    for item in available:
        for n in range(1, min(3, item["max_quantity"]) + 1):
            for required in required_choices(item):
                for location in LOCATIONS:
                    selected = list(required)
                    singles.append(
                        {
                            "item": item,
                            "selected": selected,
                            "n": n,
                            "location": location,
                            "vendor_id": item["vendor_id"],
                            "items": [line(item, selected, n)],
                            "key": gold_key(
                                item["vendor_id"], location, [line(item, selected, n)]
                            ),
                            "phrase": item_phrase(item, selected, n),
                        }
                    )
                if n != 2 or not any(not group["required"] for group in item["option_groups"]):
                    continue
                for extra in optional_singles(item):
                    if not extra:
                        continue
                    for location in LOCATIONS:
                        plain = [line(item, required, 1)]
                        modified = [line(item, required + extra, 1)]
                        items = plain + modified
                        splits.append(
                            {
                                "item": item,
                                "selected": required,
                                "extra": extra,
                                "n": 2,
                                "location": location,
                                "vendor_id": item["vendor_id"],
                                "items": items,
                                "key": gold_key(item["vendor_id"], location, items),
                                "phrase": (
                                    f"two {pluralize(item['name'].lower(), 2)}, "
                                    f"one {item_phrase(item, required + extra, 1).split(' ', 1)[-1]} "
                                    f"and one {item_phrase(item, required, 1).split(' ', 1)[-1]}"
                                ),
                            }
                        )
    # Stable, readable order rather than a random shuffle.
    singles.sort(key=lambda record: (record["item"]["id"], record["n"], record["location"], record["phrase"]))
    splits.sort(key=lambda record: (record["item"]["id"], record["location"], record["phrase"]))
    return singles, splits


def dialogue(index, category, source_group, utterance, replies, record):
    return {
        "dialogue_id": f"dialogue-{index:04d}",
        "category": category,
        "source_group": source_group,
        "initial_utterance": utterance,
        "clarification_replies": replies,
        "gold_order": {
            "vendor_id": record["vendor_id"],
            "delivery_location": record["location"],
            "items": record["items"],
        },
        "_record": record,
    }


def _lookup(singles):
    return {
        (record["item"]["id"], record["n"], tuple(record["selected"]), record["location"]): record
        for record in singles
    }


def _pull(record, used, utterances, utterance, replies, source_group, bucket):
    if record is None or record["key"] in used or utterance in utterances:
        return False
    used.add(record["key"])
    utterances.add(utterance)
    bucket.append((utterance, replies, record, source_group))
    return True


def generate():
    payload, available = load_menu()
    singles, splits = build_records(available)
    found = _lookup(singles)
    used = set()
    utterances = set()

    def grab(item_id, n, selected, location):
        return found.get((item_id, n, tuple(selected), location))

    unavailable = []
    patterns = [
        ("A large lemonade to {loc}.", "Regular is fine.", "201", [("Size", "Regular")], 1),
        ("Two large lemonades to {loc}.", "Make both of them regular.", "201", [("Size", "Regular")], 2),
        ("A diet cola to {loc}.", "A regular cola instead.", "202", [("Size", "Regular")], 1),
        ("A vanilla cola to {loc}.", "A large cola instead.", "202", [("Size", "Large")], 1),
        ("A sweet tea to {loc}.", "A regular iced tea instead.", "203", [("Size", "Regular")], 1),
        ("Two sweet teas to {loc}.", "Two large iced teas instead.", "203", [("Size", "Large")], 2),
        ("A cappuccino to {loc}.", "A small coffee instead.", "204", [("Size", "Small")], 1),
        ("An iced latte to {loc}.", "A large coffee instead.", "204", [("Size", "Large")], 1),
        ("A milkshake to {loc}.", "A regular hot chocolate instead.", "208", [("Size", "Regular")], 1),
        ("A large hot cocoa to {loc}.", "A large hot chocolate.", "208", [("Size", "Large")], 1),
        ("A bagel with jam to {loc}.", "A bagel with butter instead.", "207", [("Spread", "Butter")], 1),
        ("A bagel with peanut butter to {loc}.", "A bagel with cream cheese instead.", "207", [("Spread", "Cream cheese")], 1),
        ("The seasonal soup to {loc}.", "A grilled cheese instead.", "110", [], 1),
        ("Cheese fries to {loc}.", "One order of large fries instead.", "106", [("Size", "Large")], 1),
        ("Small fries to {loc}.", "One order of regular fries instead.", "106", [("Size", "Regular")], 1),
        ("Chicken tenders with ketchup to {loc}.", "Chicken tenders with ranch instead.", "108", [("Dipping sauce", "Ranch")], 1),
        ("Chicken tenders with garlic sauce to {loc}.", "Chicken tenders with BBQ instead.", "108", [("Dipping sauce", "BBQ")], 1),
        ("Chicken tenders with honey to {loc}.", "Chicken tenders with honey mustard instead.", "108", [("Dipping sauce", "Honey mustard")], 1),
        ("Mozzarella sticks to {loc}.", "One order of regular onion rings instead.", "109", [("Size", "Regular")], 1),
        ("A meatball sub to {loc}.", "Garlic knots instead.", "404", [], 1),
        ("A pineapple pizza to {loc}.", "A personal cheese pizza instead.", "401", [("Size", "Personal")], 1),
        ("A gluten-free pepperoni pizza to {loc}.", "A large pepperoni pizza instead.", "402", [("Size", "Large")], 1),
        ("An acai bowl to {loc}.", "A regular berry smoothie instead.", "501", [("Size", "Regular")], 1),
        ("A protein shake to {loc}.", "A large green smoothie instead.", "502", [("Size", "Large")], 1),
        ("A poke bowl to {loc}.", "A chicken rice bowl with teriyaki instead.", "503", [("Sauce", "Teriyaki")], 1),
        ("A caesar salad to {loc}.", "A garden salad with ranch instead.", "303", [("Dressing", "Ranch")], 1),
        ("A fish sandwich to {loc}.", "A turkey sandwich on wheat instead.", "302", [("Bread", "Wheat")], 1),
        ("A wrap with bacon to {loc}.", "A veggie wrap on a wheat wrap instead.", "301", [("Bread", "Wheat wrap")], 1),
        ("Nacho cheese chips to {loc}.", "Plain potato chips instead.", "305", [("Flavor", "Plain")], 1),
        ("A beyond burger to {loc}.", "A veggie burger instead.", "104", [], 1),
    ]
    for location in LOCATIONS:
        for utterance, reply, item_id, selected, n in patterns:
            if len(unavailable) == 200:
                break
            _pull(
                grab(item_id, n, selected, location),
                used,
                utterances,
                utterance.format(loc=location),
                [reply],
                f"unavailable:{item_id}",
                unavailable,
            )
        if len(unavailable) == 200:
            break

    ambiguous = []
    family_members = {}
    for item_id, vague in VAGUE.items():
        family_members.setdefault(vague, []).append(item_id)
    for location in LOCATIONS:
        for vague, members in family_members.items():
            for n in (1, 2):
                for member_id in members:
                    if len(ambiguous) == 200:
                        break
                    item = next(item for item in available if item["id"] == member_id)
                    required = required_choices(item)[0]
                    record = grab(member_id, n, required, location)
                    if n == 1:
                        vague_phrase = f"{article(vague)} {vague}"
                    else:
                        vague_phrase = f"{QTY_WORDS[n]} {pluralize(vague, n)}"
                    utterance = None
                    for tail in ("", " please", " today", " for lunch"):
                        candidate = f"I'll have {vague_phrase}{tail}, deliver to {location}."
                        if candidate not in utterances:
                            utterance = candidate
                            break
                    if utterance is None or record is None:
                        continue
                    _pull(
                        record,
                        used,
                        utterances,
                        utterance,
                        [f"{record['phrase'].capitalize()}."],
                        f"ambiguous:{vague}",
                        ambiguous,
                    )
                if len(ambiguous) == 200:
                    break
            if len(ambiguous) == 200:
                break
        if len(ambiguous) == 200:
            break

    customization = []
    for location in LOCATIONS:
        for item in available:
            if len(customization) >= 100:
                break
            if not any(group["required"] for group in item["option_groups"]):
                continue
            required = required_choices(item)[0]
            record = grab(item["id"], 1, required, location)
            _pull(
                record,
                used,
                utterances,
                f"Could I get {item_phrase(item, [], 1)} delivered to {location}?",
                [f"{record['phrase'].capitalize()}." if record else ""],
                f"custom:missing:{item['id']}",
                customization,
            )
    split_groups = {}
    for record in splits:
        split_groups.setdefault(record["item"]["id"], []).append(record)
    split_queues = list(split_groups.values())
    while len(customization) < 200:
        progressed = False
        for queue in split_queues:
            if len(customization) == 200:
                break
            while queue:
                record = queue.pop(0)
                extra_text = " and ".join(option.lower() for _, option in record["extra"])
                size, flavor, plain_spread, extras = selected_bits(record["selected"])
                name = pluralize(record["item"]["name"].lower(), 2)
                if size:
                    name = f"{size} {name}"
                if plain_spread:
                    name = f"plain {name}"
                shared = f" {' and '.join(extras)}" if extras else ""
                utterance = (
                    f"Two {name}{shared}, one of them with {extra_text}, "
                    f"deliver to {record['location']}."
                )
                if _pull(
                    record,
                    used,
                    utterances,
                    utterance,
                    [],
                    f"custom:split:{record['item']['id']}",
                    customization,
                ):
                    progressed = True
                    break
        if not progressed:
            break

    corrections = []
    for location in LOCATIONS:
        for item in available:
            if len(corrections) >= 100:
                break
            required = required_choices(item)[0]
            before = grab(item["id"], 1, required, location)
            after = grab(item["id"], 2, required, location)
            if before is None or after is None or after["key"] in used:
                continue
            utterance = f"{before['phrase'].capitalize()} to {location}."
            _pull(
                after,
                used,
                utterances,
                utterance,
                ["Actually, make that two."],
                f"correction:quantity:{item['id']}",
                corrections,
            )
    for index, location in enumerate(LOCATIONS):
        destination = LOCATIONS[(index + 1) % len(LOCATIONS)]
        for item in available:
            if len(corrections) == 200:
                break
            required = required_choices(item)[0]
            before = grab(item["id"], 1, required, location)
            after = grab(item["id"], 1, required, destination)
            if before is None or after is None or after["key"] in used:
                continue
            utterance = f"Please send {before['phrase']} to {location}."
            reply = f"Deliver it to {destination} instead."
            _pull(
                after,
                used,
                utterances,
                utterance,
                [reply],
                f"correction:location:{item['id']}",
                corrections,
            )
        if len(corrections) == 200:
            break

    by_vendor = {}
    for item in available:
        by_vendor.setdefault(item["vendor_id"], []).append(item)
    for location in LOCATIONS:
        for items in by_vendor.values():
            for source in items:
                if len(corrections) == 200:
                    break
                source_choices = required_choices(source)
                before = grab(source["id"], 1, source_choices[0], location)
                if before is None:
                    continue
                utterance = f"I want {before['phrase']} sent to {location}."
                if utterance in utterances:
                    continue
                placed = False
                for target in items:
                    if target["id"] == source["id"]:
                        continue
                    for n in (1, 2, 3):
                        if n > target["max_quantity"]:
                            continue
                        for choice in required_choices(target):
                            after = grab(target["id"], n, choice, location)
                            if _pull(
                                after,
                                used,
                                utterances,
                                utterance,
                                [f"Change that to {after['phrase']}." if after else ""],
                                f"correction:swap:{target['id']}",
                                corrections,
                            ):
                                placed = True
                                break
                        if placed:
                            break
                    if placed:
                        break
            if len(corrections) == 200:
                break
        if len(corrections) == 200:
            break

    clear = []
    queues = []
    for item in available:
        queue = []
        for n in (1, 2, 3):
            if n > item["max_quantity"]:
                continue
            for required in required_choices(item):
                for location in LOCATIONS:
                    queue.append(grab(item["id"], n, required, location))
        queues.append([record for record in queue if record is not None])
    while len(clear) < 200:
        progressed = False
        for queue in queues:
            while queue and len(clear) < 200:
                record = queue.pop(0)
                utterance = f"I'd like {record['phrase']}, delivered to {record['location']}."
                if _pull(record, used, utterances, utterance, [], f"clear:{record['item']['id']}", clear):
                    progressed = True
                    break
        if not progressed:
            break

    groups = [
        ("clear_request", clear),
        ("ambiguous_item", ambiguous),
        ("unavailable_option", unavailable),
        ("customization", customization),
        ("correction", corrections),
    ]
    for name, rows in groups:
        if len(rows) != 200:
            raise RuntimeError(f"{name} produced {len(rows)} dialogues, expected 200.")

    ordered = []
    for category, rows in groups:
        for utterance, replies, record, source_group in rows:
            ordered.append((category, utterance, replies, record, source_group))

    item_lookup = {item["id"]: item for item in payload["items"]}
    vendors = {vendor["id"]: vendor["name"] for vendor in payload["vendors"]}
    dialogues = []
    for index, (category, utterance, replies, record, source_group) in enumerate(ordered, start=1):
        row = dialogue(index, category, source_group, utterance, replies, record)
        row["gold_english"] = english_gold(
            item_lookup, record["vendor_id"], record["location"], record["items"], vendors
        )
        dialogues.append(row)
    return payload, dialogues



def write_jsonl(dialogues):
    lines = []
    for row in dialogues:
        payload = {
            "dialogue_id": row["dialogue_id"],
            "category": row["category"],
            "source_group": row["source_group"],
            "initial_utterance": row["initial_utterance"],
            "clarification_replies": row["clarification_replies"],
            "gold_order": row["gold_order"],
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    JSONL_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_doc(payload, dialogues):
    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    document.add_heading("Campus menu and annotated orders", level=0)
    document.add_paragraph(
        "This file is a plain-English copy of the frozen menu and 1,000 annotated ordering dialogues. "
        "The gold order is the order the customer actually wants after any clarification or correction. "
        "It is the answer key, not the order the model produced."
    )

    document.add_heading("Menu snapshot", level=1)
    document.add_paragraph(
        "Synthetic campus menu used for these dialogues. It is not an export from the live database. "
        "Items marked unavailable are on the menu so the assistant can be asked for something it must refuse."
    )
    by_vendor = {}
    for item in payload["items"]:
        by_vendor.setdefault(item["vendor_id"], []).append(item)
    vendor_meta = {vendor["id"]: vendor for vendor in payload["vendors"]}
    for vendor_id, items in by_vendor.items():
        vendor = vendor_meta[vendor_id]
        document.add_heading(f"{vendor['name']} ({vendor['location_label']})", level=2)
        for item in items:
            status = "Unavailable. " if not item["available"] else ""
            if item["option_groups"]:
                groups = []
                for group in item["option_groups"]:
                    requirement = "required" if group["required"] else "optional"
                    groups.append(
                        f"{group['name']} ({requirement}): {', '.join(group['options'])}"
                    )
                options = " Options: " + "; ".join(groups) + "."
            else:
                options = " No options."
            document.add_paragraph(
                f"{item['name']} — ${item['price']}. {status}Maximum quantity {item['max_quantity']}.{options}",
                style="List Bullet",
            )

    document.add_heading("Annotated dialogues", level=1)
    labels = {
        "clear_request": "Clear requests",
        "ambiguous_item": "Ambiguous items",
        "unavailable_option": "Unavailable options",
        "customization": "Customizations",
        "correction": "Corrections",
    }
    current = None
    for index, row in enumerate(dialogues, start=1):
        if row["category"] != current:
            current = row["category"]
            document.add_heading(labels[current], level=2)
        follow = row["clarification_replies"][0] if row["clarification_replies"] else "None."
        pretty = {
            "clear_request": "Clear request",
            "ambiguous_item": "Ambiguous item",
            "unavailable_option": "Unavailable option",
            "customization": "Customization",
            "correction": "Correction",
        }[row["category"]]
        document.add_paragraph(f"{index}. {pretty}")
        document.add_paragraph(f"Customer: {row['initial_utterance']}")
        document.add_paragraph(f"If asked: {follow}")
        document.add_paragraph(f"Gold: {row['gold_english']}")

    document.save(DOC_PATH)


def main():
    payload, dialogues = generate()
    write_jsonl(dialogues)
    write_doc(payload, dialogues)
    print(f"dialogues={len(dialogues)}")
    print(f"jsonl={JSONL_PATH}")
    print(f"docx={DOC_PATH}")


if __name__ == "__main__":
    main()
