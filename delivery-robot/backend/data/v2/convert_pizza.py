"""Convert human-written PIZZA dev/test orders into dialogues on menu_snapshot_b.json.

Only orders that the Slice Factory vendor (id 6) can represent exactly are kept;
the rest are dropped and counted. The customer's text is kept as written. The
output contains PIZZA text (CC BY-NC 4.0), so it is written under
data/external/ (git-ignored) and regenerated locally from the downloads:

    python convert_pizza.py ../external/raw/PIZZA_test.json ../external/raw/PIZZA_dev.json \
        --out ../external/pizza_human.jsonl --sample 300
"""

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

LOCATIONS = [
    "Sprague Library", "Student Center", "University Hall", "Blanton Hall",
    "Recreation Center", "Dickson Hall", "Calcia Hall", "Freeman Hall",
    "Richardson Hall", "Partridge Hall", "Life Hall", "College Hall",
]
PIZZA_ID = "601"
SIZES = {"SMALL": "Small", "MEDIUM": "Medium", "LARGE": "Large", "EXTRA_LARGE": "Extra large"}
CRUSTS = {"THIN_CRUST": "Thin crust", "DEEP_DISH": "Deep dish", "STUFFED_CRUST": "Stuffed crust",
          "GLUTEN_FREE_CRUST": "Gluten-free crust"}
TOPPINGS = {
    "PEPPERONI": "Pepperoni", "SAUSAGE": "Sausage", "ITALIAN_SAUSAGE": "Sausage", "HAM": "Ham",
    "BACON": "Bacon", "CHICKEN": "Chicken", "TUNA": "Tuna", "SALAMI": "Salami", "ANCHOVIES": "Anchovies",
    "MUSHROOMS": "Mushrooms", "ONIONS": "Onions", "PEPPERS": "Peppers", "GREEN_PEPPERS": "Peppers",
    "OLIVES": "Olives", "PINEAPPLE": "Pineapple", "SPINACH": "Spinach", "PESTO": "Pesto",
}
DRINKS = {"COKE": "602", "DIET_COKE": "603", "PEPSI": "604", "DIET_PEPSI": "605", "SPRITE": "606",
          "DIET_SPRITE": "607", "FANTA": "608", "DR_PEPPER": "609", "ICE_TEA": "610",
          "DIET_ICE_TEA": "611", "MOUNTAIN_DEW": "612", "WATER": "613"}
MAX_QUANTITY = 10
MAX_TOPPINGS = 5


class Skip(Exception):
    pass


def parse(text):
    tokens = re.findall(r"\(|\)|[^\s()]+", text)
    pos = 0

    def node():
        nonlocal pos
        pos += 1
        label = tokens[pos]
        pos += 1
        kids, words = [], []
        while tokens[pos] != ")":
            if tokens[pos] == "(":
                kids.append(node())
            else:
                words.append(tokens[pos])
                pos += 1
        pos += 1
        return {"label": label, "kids": kids, "value": " ".join(words)}

    return node()


def number(node):
    value = node["value"]
    if not value.isdigit() or not 1 <= int(value) <= MAX_QUANTITY:
        raise Skip("quantity")
    return int(value)


def pizza_line(order):
    n, size, crust, toppings = 1, None, None, []
    for kid in order["kids"]:
        label = kid["label"]
        if label == "NUMBER":
            n = number(kid)
        elif label == "SIZE":
            if kid["value"] not in SIZES:
                raise Skip(f"size:{kid['value']}")
            size = SIZES[kid["value"]]
        elif label == "STYLE":
            if kid["value"] not in CRUSTS:
                raise Skip(f"style:{kid['value']}")
            crust = CRUSTS[kid["value"]]
        elif label == "TOPPING":
            if kid["value"] not in TOPPINGS:
                # Plain "cheese" is on every pizza; anything else is not on our menu.
                raise Skip(f"topping:{kid['value']}")
            toppings.append(TOPPINGS[kid["value"]])
        elif label == "COMPLEX_TOPPING":
            q = next((k["value"] for k in kid["kids"] if k["label"] == "QUANTITY"), None)
            t = next((k["value"] for k in kid["kids"] if k["label"] == "TOPPING"), None)
            if q == "EXTRA" and t == "CHEESE":
                toppings.append("Extra cheese")
            else:
                raise Skip(f"complex:{q}:{t}")
        elif label == "NOT":
            # "no pineapple" on a build-your-own pizza: nothing to add. Kept as a
            # test that the assistant does not add it.
            if any(k["label"] != "TOPPING" for k in kid["kids"]):
                raise Skip("not:style")
        else:
            raise Skip(f"pizza:{label}")
    toppings = sorted(set(toppings), key=toppings.index)
    if len(toppings) > MAX_TOPPINGS:
        raise Skip("too_many_toppings")
    return n, size, crust, toppings


def drink_line(order):
    n, item = 1, None
    for kid in order["kids"]:
        if kid["label"] == "NUMBER":
            n = number(kid)
        elif kid["label"] == "DRINKTYPE":
            if kid["value"] not in DRINKS:
                raise Skip(f"drink:{kid['value']}")
            item = DRINKS[kid["value"]]
        else:
            raise Skip(f"drink:{kid['label']}")
    return {"menu_item_id": item, "quantity": n, "customizations": []}


def convert(src, exr, rng):
    tree = parse(exr)
    pizzas, drinks = [], []
    for order in tree["kids"]:
        if order["label"] == "PIZZAORDER":
            pizzas.append(pizza_line(order))
        elif order["label"] == "DRINKORDER":
            drinks.append(drink_line(order))
        else:
            raise Skip(order["label"])
    sizeless = [p for p in pizzas if p[1] is None]
    if len(sizeless) > 1:
        raise Skip("several_sizeless_pizzas")
    replies = []
    lines = []
    for n, size, crust, toppings in pizzas:
        if size is None:
            size = rng.choice(list(SIZES.values()))
            replies.append(rng.choice([f"{size}, please.", f"{size.lower()} please.", f"Make it {size.lower()}."]))
        lines.append({"menu_item_id": PIZZA_ID, "quantity": n,
                      "customizations": [size] + ([crust] if crust else []) + toppings})
    lines += drinks
    merged = {}
    for line in lines:
        key = (line["menu_item_id"], tuple(sorted(line["customizations"])))
        if key in merged:
            merged[key]["quantity"] += line["quantity"]
        else:
            merged[key] = dict(line)
    lines = list(merged.values())
    if any(line["quantity"] > MAX_QUANTITY for line in lines):
        raise Skip("quantity")
    location = rng.choice(LOCATIONS)
    # Ask for the location only when nothing else is missing, so the scripted
    # replies do not depend on which question the assistant asks first.
    if not replies and rng.random() < 0.3:
        utterance = src
        replies = [rng.choice([f"Deliver it to {location}.", f"To {location}, please."])]
    else:
        utterance = f"{src}, deliver to {location}"
    return utterance, replies, {"vendor_id": 6, "delivery_location": location, "items": lines}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--sample", type=int, default=300)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    kept, skipped = [], Counter()
    for path in args.inputs:
        split = Path(path).stem
        for index, raw in enumerate(open(path, encoding="utf-8")):
            row = json.loads(raw)
            src = next(v for k, v in row.items() if k.endswith(".SRC"))
            exr = next(v for k, v in row.items() if k.endswith(".EXR"))
            try:
                utterance, replies, gold = convert(src, exr, rng)
            except Skip as reason:
                skipped[str(reason).split(":")[0]] += 1
                continue
            kept.append({
                "category": "pizza_human",
                "source_group": f"{split}:{index}",
                "initial_utterance": utterance,
                "clarification_replies": replies,
                "gold_order": gold,
            })
    rng.shuffle(kept)
    sample = kept[: args.sample]
    with open(args.out, "w", encoding="utf-8") as handle:
        for number_, row in enumerate(sample, start=1):
            row = {"dialogue_id": f"pizza-{number_:04d}", **row}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"kept {len(kept)}, skipped {sum(skipped.values())} {dict(skipped)}; wrote {len(sample)} to {args.out}")


if __name__ == "__main__":
    main()
