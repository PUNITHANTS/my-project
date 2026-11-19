"""Write data/v2/menu_snapshot_b.json: the held-out menu (vendors never used in v1)."""
import json
import sys
from pathlib import Path

VENDORS = [
    {"id": 6, "name": "Slice Factory", "location_label": "Partridge Hall"},
    {"id": 7, "name": "Taco Loco", "location_label": "Student Center"},
    {"id": 8, "name": "Boba Bar", "location_label": "Sprague Library"},
    {"id": 9, "name": "Curry Corner", "location_label": "University Hall"},
]
vendor_by_id = {v["id"]: v for v in VENDORS}
_gid = [0]


def group(name, options, required=False, max_selections=1):
    _gid[0] += 1
    return {
        "id": 9000 + _gid[0],
        "name": name,
        "required": required,
        "min_selections": 1 if required else 0,
        "max_selections": max_selections,
        "options": options,
    }


def item(item_id, name, vendor_id, price, groups=(), available=True, max_quantity=6, description=""):
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


# Slice Factory mirrors the PIZZA dataset: build-your-own pizza plus fountain drinks.
PIZZA_TOPPINGS = [
    "Pepperoni", "Sausage", "Ham", "Bacon", "Chicken", "Tuna", "Salami", "Anchovies",
    "Mushrooms", "Onions", "Peppers", "Olives", "Pineapple", "Spinach", "Pesto", "Extra cheese",
]
DRINKS = [
    "Coke", "Diet Coke", "Pepsi", "Diet Pepsi", "Sprite", "Diet Sprite", "Fanta", "Dr Pepper",
    "Iced Tea", "Diet Iced Tea", "Mountain Dew", "Water",
]
items = [
    item(601, "Pizza", 6, "11.00", [
        group("Size", ["Small", "Medium", "Large", "Extra large"], required=True),
        group("Crust", ["Thin crust", "Deep dish", "Stuffed crust", "Gluten-free crust"]),
        group("Toppings", PIZZA_TOPPINGS, max_selections=5),
    ], max_quantity=10, description="Build your own pizza."),
]
for offset, name in enumerate(DRINKS, start=2):
    items.append(item(600 + offset, name, 6, "2.00", max_quantity=10))
items.append(item(620, "Garlic Bread", 6, "4.00", available=False))

TACO_SALSA = group("Extras", ["Mild salsa", "Hot salsa", "Guacamole", "No cheese"], max_selections=2)
items += [
    item(701, "Chicken Taco", 7, "3.50", [group("Tortilla", ["Corn", "Flour"], required=True), dict(TACO_SALSA, id=9101)]),
    item(702, "Steak Taco", 7, "4.00", [group("Tortilla", ["Corn", "Flour"], required=True), dict(TACO_SALSA, id=9102)]),
    item(703, "Veggie Taco", 7, "3.25", [group("Tortilla", ["Corn", "Flour"], required=True), dict(TACO_SALSA, id=9103)]),
    item(704, "Burrito Bowl", 7, "9.50", [
        group("Protein", ["Chicken", "Steak", "Sofritas"], required=True),
        group("Rice", ["White rice", "Brown rice"], required=True),
        group("Toppings", ["Black beans", "Corn salsa", "Sour cream", "Guacamole"], max_selections=3),
    ], max_quantity=4),
    item(705, "Chips and Salsa", 7, "3.00"),
    item(706, "Quesadilla", 7, "7.00", [group("Filling", ["Cheese", "Chicken", "Steak"], required=True)], max_quantity=4),
    item(707, "Churros", 7, "4.00", available=False),
]

MILK_TEA = [
    group("Sweetness", ["No sugar", "Half sugar", "Full sugar"], required=True),
    group("Ice", ["No ice", "Less ice", "Regular ice"], required=True),
    group("Toppings", ["Boba", "Lychee jelly", "Pudding"], max_selections=2),
]


def copy_groups(groups):
    out = []
    for g in groups:
        _gid[0] += 1
        out.append(dict(g, id=9000 + _gid[0], options=list(g["options"])))
    return out


items += [
    item(801, "Classic Milk Tea", 8, "5.00", copy_groups(MILK_TEA), max_quantity=4),
    item(802, "Taro Milk Tea", 8, "5.50", copy_groups(MILK_TEA), max_quantity=4),
    item(803, "Matcha Milk Tea", 8, "5.75", copy_groups(MILK_TEA), max_quantity=4),
    item(804, "Mango Fruit Tea", 8, "5.25", [group("Ice", ["No ice", "Less ice", "Regular ice"], required=True)], max_quantity=4),
    item(805, "Passion Fruit Tea", 8, "5.25", [group("Ice", ["No ice", "Less ice", "Regular ice"], required=True)], max_quantity=4),
    item(806, "Brown Sugar Milk Tea", 8, "6.00", copy_groups(MILK_TEA), available=False, max_quantity=4),
]

CURRY = [
    group("Spice level", ["Mild", "Medium", "Hot"], required=True),
    group("Side", ["Rice", "Naan"], required=True),
]
items += [
    item(901, "Chicken Curry", 9, "10.50", copy_groups(CURRY), max_quantity=4),
    item(902, "Lamb Curry", 9, "12.00", copy_groups(CURRY), max_quantity=4),
    item(903, "Chickpea Curry", 9, "9.50", copy_groups(CURRY), max_quantity=4),
    item(904, "Samosas", 9, "4.50", max_quantity=5),
    item(905, "Mango Lassi", 9, "4.00", [group("Size", ["Regular", "Large"], required=True)], max_quantity=5),
    item(906, "Garlic Naan", 9, "3.00", max_quantity=5),
    item(907, "Paneer Curry", 9, "11.00", copy_groups(CURRY), available=False, max_quantity=4),
]

payload = {
    "generated_at": "2026-11-19T00:00:00+00:00",
    "source": "synthetic held-out campus menu for dataset v2 (vendors not in menu_snapshot_v1; not from production)",
    "vendors": VENDORS,
    "items": items,
}
out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(len(items), "items")
