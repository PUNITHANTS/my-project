"""Write data/v3/menu_snapshot_v3.json: the frozen menu for dataset v3.

Menu A (``data/menu_snapshot_v1.json``) + menu B (``data/v2/menu_snapshot_b.json``),
with these changes:

* Blanton Pizza (vendor 4) is dropped. Its pizzas would make every PIZZA order
  ("a large pepperoni pizza") ambiguous with Slice Factory, whose answer key the
  External-P holdout assumes.
* Library Cafe's "Iced Tea" (203) becomes "Iced Green Tea", so Slice Factory's
  "Iced Tea" (PIZZA's ICE_TEA) stays the only item of that name.
* Two new restaurants. Each sells one or two items whose names another
  restaurant also uses (Fries, Veggie Burger, Garden Salad, Berry Smoothie), so
  "which restaurant?" can be tested. Their other items add required option
  pairs and one unavailable item each.

Item and group ids from menus A and B are unchanged, so their dialogues' gold
orders still refer to the same items.
"""

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent

menu_a = json.loads((DATA / "menu_snapshot_v1.json").read_text(encoding="utf-8"))
menu_b = json.loads((DATA / "v2" / "menu_snapshot_b.json").read_text(encoding="utf-8"))

NEW_VENDORS = [
    {"id": 10, "name": "Night Owl Diner", "location_label": "Life Hall"},
    {"id": 11, "name": "Green Bowl", "location_label": "College Hall"},
]
vendors = [v for v in menu_a["vendors"] if v["id"] != 4] + menu_b["vendors"] + NEW_VENDORS
vendor_by_id = {v["id"]: v for v in vendors}

items = []
for item in menu_a["items"] + menu_b["items"]:
    if item["vendor_id"] == 4:
        continue
    item = copy.deepcopy(item)
    if item["id"] == "203":
        item["name"] = "Iced Green Tea"
    items.append(item)

_gid = [11000]


def group(name, options, required=False, max_selections=1):
    _gid[0] += 1
    return {
        "id": _gid[0],
        "name": name,
        "required": required,
        "min_selections": 1 if required else 0,
        "max_selections": max_selections,
        "options": list(options),
    }


def item(item_id, name, vendor_id, price, groups=(), available=True, max_quantity=5, description=""):
    v = vendor_by_id[vendor_id]
    return {
        "id": str(item_id),
        "name": name,
        "description": description,
        "price": price,
        "vendor_id": vendor_id,
        "vendor": v["name"],
        "vendor_location": v["location_label"],
        "available": available,
        "max_quantity": max_quantity,
        "option_groups": list(groups),
    }


items += [
    # Night Owl Diner: Fries and Veggie Burger share names with Red Hawk Grill.
    item(1001, "Fries", 10, "3.75", [group("Size", ["Regular", "Large"], required=True)]),
    item(1002, "Veggie Burger", 10, "9.00", [group("Sauce", ["Mayo", "No mayo", "Ketchup", "Hot sauce"], max_selections=2)]),
    item(1003, "Pancakes", 10, "6.50", [
        group("Topping", ["Maple syrup", "Strawberries", "Chocolate chips"], required=True),
        group("Stack", ["Short stack", "Full stack"], required=True),
    ], max_quantity=4),
    item(1004, "Breakfast Sandwich", 10, "6.00", [
        group("Bread", ["Bagel", "English muffin", "Croissant"], required=True),
        group("Add-ons", ["Bacon", "Sausage", "No cheese"], max_selections=2),
    ]),
    item(1005, "Hash Browns", 10, "2.75"),
    item(1006, "Omelette", 10, "7.50", available=False, max_quantity=3),
    # Green Bowl: Garden Salad and Berry Smoothie share names with Campus Deli
    # and Hawk Smoothie Bar.
    item(1101, "Grain Bowl", 11, "11.50", [
        group("Protein", ["Salmon", "Tofu", "Chicken"], required=True),
        group("Base", ["Brown rice", "Quinoa", "Greens"], required=True),
        group("Toppings", ["Avocado", "Edamame", "Cucumber", "Corn"], max_selections=3),
    ], max_quantity=4),
    item(1102, "Hummus Wrap", 11, "8.00", [group("Bread", ["White wrap", "Wheat wrap"], required=True)]),
    item(1103, "Garden Salad", 11, "7.25", [group("Dressing", ["Ranch", "Balsamic", "No dressing"], required=True)], max_quantity=4),
    item(1104, "Berry Smoothie", 11, "6.25", [group("Size", ["Regular", "Large"], required=True)], max_quantity=3),
    item(1105, "Kombucha", 11, "4.50", available=False),
]

payload = {
    "version": "v3",
    "generated_at": "2026-11-20T00:00:00+00:00",
    "source": (
        "synthetic campus menu for dataset v3: menu A without Blanton Pizza, menu B, and two new "
        "restaurants (not exported from production)"
    ),
    "vendors": vendors,
    "items": items,
}
out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "menu_snapshot_v3.json"
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
ids = [i["id"] for i in items]
assert len(ids) == len(set(ids)), "duplicate item ids"
gids = [g["id"] for i in items for g in i["option_groups"]]
assert len(gids) == len(set(gids)), "duplicate group ids"
print(f"{len(vendors)} vendors, {len(items)} items ({sum(not i['available'] for i in items)} unavailable) -> {out}")
