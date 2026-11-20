"""Dataset v3: ~1000 dialogues on menu_snapshot_v3.json, inspired by human PIZZA orders.

Leakage rules (see README.md):
* External-P (100 PIZZA orders, ids in external_p_source_ids.json) is never read.
* Seed-P (the 300 PIZZA orders in data/external/pizza_human.jsonl) is split into
  train/validation/test seed pools *before* generation. Every dialogue is built
  from one seed of its own split's pool and records it as ``source_group``, so a
  seed's family never crosses splits.
* Train and validation use the v2 dev sentence templates; test uses only the v2
  test templates, so Test-200 wording is not seen in training.

How a seed shapes a dialogue:
* ``pizza_seed``: the seed's own text with one detail changed (a topping, the
  size, a drink or a quantity), edited by a local model and checked word by
  word. The gold order is the seed's gold with the same change.
* every other category: a menu-driven dialogue (generate_v2.Builder) whose
  first message is rewritten in the seed customer's style. The rewrite is kept
  only if every item, option, quantity and place survives; otherwise the
  template text is kept (``restyled`` false).
"""

from __future__ import annotations

import json
import random
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "v2"))

import paraphrase  # noqa: E402
from generate_v2 import (  # noqa: E402
    LOCATIONS, NUMBER_WORDS, R, T, Builder, Menu, count, fill, gold_line, phrase, pick_required,
)

GEN_MODEL = "qwen3.5:9b"
SPLIT_SIZES = {"train": 600, "validation": 200, "test": 200}
SEED_SHARES = {"train": 180, "validation": 60, "test": 60}
CATEGORIES = ["clear_request", "ambiguous_item", "unavailable_option", "customization", "correction",
              "removal", "multi_item", "multi_problem", "quantity_limit", "partial_answer",
              "same_name", "pizza_seed"]

T["same_name"] = {
    "dev": ["{Order} to {loc}, please.", "Can I get {order} delivered to {loc}?"],
    "test": ["Hey, could {loc} get {order}?", "I'm at {loc}. {Order}, please."],
}
R["vendor"] = {"dev": ["From {vendor}.", "The one from {vendor}."], "test": ["{vendor}, please.", "Let's go with {vendor}."]}

STYLE_PROMPT = (
    "Below is an order message a real customer typed into a food-ordering kiosk, and then a new order "
    "message. Rewrite the new message so it reads as if the same customer typed it: the same casing, "
    "punctuation habits and kind of wording. Keep every food item, quantity, option and place name of "
    "the new message with the same words. Do not copy any food from the example. Reply with only the "
    "rewritten message.\n\nExample customer message: {seed}\nNew message: {text}"
)
EDIT_PROMPT = (
    "Here is a pizza order a customer typed. Edit it so it orders {new} instead of {old}. Change only "
    "the words needed for that; keep everything else exactly as written, including spelling and "
    "lower case. Reply with only the edited message.\n\nMessage: {text}"
)
SIZES = ["Small", "Medium", "Large", "Extra large"]
TOPPING_WORDS = {"Peppers": "green peppers", "Olives": "olives", "Extra cheese": "extra cheese"}


def chat(prompt, seed, model=GEN_MODEL):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False,
            "think": False, "options": {"temperature": 0.7, "seed": seed, "num_predict": 160}}
    request = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        content = json.loads(response.read())["message"]["content"]
    return content.strip().strip('"').strip()


def plain(text):
    return bool(text) and all(ord(ch) < 128 for ch in text)


def seed_text(seed):
    """The customer's own words, without the location the converter appended."""
    return re.sub(r",\s*deliver to [A-Z][\w ]+$", "", seed["initial_utterance"]).strip()


class V3Builder(Builder):
    """v2 categories on the general menu, plus same-name dialogues on the full menu."""

    def __init__(self, general, full, split, rng):
        super().__init__(general, split, rng)
        self.full = full
        by_name = {}
        for item in full.items:
            by_name.setdefault(item["name"].lower(), []).append(item)
        self.same_name = [group for group in by_name.values() if len(group) > 1]

    def same_name_dialogue(self):
        group = self.rng.choice(self.same_name)
        item = self.rng.choice(group)
        n = 1 if item["max_quantity"] < 2 else self.rng.randint(1, 2)
        selected = pick_required(self.rng, item)
        tid, t = self.tpl("same_name")
        loc = self.loc()
        lines = [gold_line(item, n, selected)]
        partners = [i for i in self.full.by_vendor[item["vendor_id"]]
                    if all(i["name"].lower() != g[0]["name"].lower() for g in self.same_name)]
        if partners and self.rng.random() < 0.35:
            # Another item from the same restaurant settles which one is meant.
            partner = self.rng.choice(partners)
            psel = pick_required(self.rng, partner)
            order = f"{phrase(self.full, item, n, selected)} and {phrase(self.full, partner, 1, psel)}"
            lines.append(gold_line(partner, 1, psel))
            replies = []
            tid += ":pinned"
        else:
            order = phrase(self.full, item, n, selected)
            replies = [self.reply("vendor", vendor=item["vendor"])]
        return self.dialogue("same_name", tid, fill(t, order=order, loc=loc), replies, item["vendor_id"], loc, lines)


class SeedEditor:
    """Turns one Seed-P order into a new dialogue by changing one detail of it."""

    def __init__(self, menu_payload, vocab, rng):
        self.items = {i["id"]: i for i in menu_payload["items"]}
        self.toppings = next(g for g in self.items["601"]["option_groups"] if g["name"] == "Toppings")["options"]
        self.drinks = [i for i in menu_payload["items"] if i["vendor_id"] == 6 and i["id"] != "601" and i["available"]]
        self.vocab, self.rng = vocab, rng

    def _check(self, original, candidate, old_words, new_words):
        if not plain(candidate) or len(candidate) > 2 * len(original) + 30 or "\n" in candidate:
            return False
        stems = lambda text: Counter(paraphrase._stem(w) for w in paraphrase._words(text))  # noqa: E731
        before, after = stems(original), stems(candidate)
        old = Counter(paraphrase._stem(w) for w in paraphrase._words(old_words))
        new = Counter(paraphrase._stem(w) for w in paraphrase._words(new_words))
        menuish = lambda c: Counter({k: v for k, v in c.items() if k in self.vocab or k in NUMBER_WORDS.values()})  # noqa: E731
        expected = menuish(before) - menuish(old) + menuish(new)
        return menuish(after) == expected and all(after[w] >= 1 for w in new)

    def make(self, seed):
        text = seed_text(seed)
        gold = json.loads(json.dumps(seed["gold_order"]))
        pizza = [line for line in gold["items"] if line["menu_item_id"] == "601"]
        kinds = []
        low = " " + text.lower() + " "
        for line in pizza:
            for top in line["customizations"]:
                word = TOPPING_WORDS.get(top, top.lower())
                if top in self.toppings and low.count(" " + paraphrase._stem(word.split()[-1])) == 1:
                    kinds.append(("topping", line, top))
            size = next((c for c in line["customizations"] if c in SIZES), None)
            if size and re.search(rf"\b{size.lower()}\b", text.lower()) and not (size == "Large" and "extra large" in text.lower()):
                kinds.append(("size", line, size))
        for line in gold["items"]:
            if line["menu_item_id"] != "601":
                kinds.append(("drink", line, self.items[line["menu_item_id"]]["name"]))
        if len(gold["items"]) == 1 and gold["items"][0]["quantity"] <= 3:
            kinds.append(("quantity", gold["items"][0], gold["items"][0]["quantity"]))
        self.rng.shuffle(kinds)
        for kind, line, old in kinds:
            if kind == "topping":
                choices = [t for t in self.toppings if t not in line["customizations"] and t != "Extra cheese"]
                new = self.rng.choice(choices)
                old_w, new_w = TOPPING_WORDS.get(old, old.lower()), new.lower()
                change = lambda l, o=old, n=new: l["customizations"].__setitem__(l["customizations"].index(o), n)  # noqa: E731
            elif kind == "size":
                new = self.rng.choice([s for s in SIZES if s != old])
                old_w, new_w = old.lower(), new.lower()
                change = lambda l, o=old, n=new: l["customizations"].__setitem__(l["customizations"].index(o), n)  # noqa: E731
            elif kind == "drink":
                current = {l["menu_item_id"] for l in gold["items"]}
                target = self.rng.choice([d for d in self.drinks if d["id"] not in current])
                old_w, new_w, new = old.lower(), target["name"].lower(), target["id"]
                change = lambda l, n=new: l.__setitem__("menu_item_id", n)  # noqa: E731
            else:
                new = self.rng.choice([q for q in (1, 2, 3) if q != old])
                old_w, new_w = ("a pizza" if old == 1 else f"{count(old)} pizzas"), ("a pizza" if new == 1 else f"{count(new)} pizzas")
                change = lambda l, n=new: l.__setitem__("quantity", n)  # noqa: E731
            for attempt in range(2):
                candidate = chat(EDIT_PROMPT.format(new=new_w, old=old_w, text=text), seed=self.rng.randrange(1 << 30))
                quantity_ok = kind != "quantity" or (NUMBER_WORDS.get(new, "") in candidate.lower() if new > 1 else not any(
                    w in candidate.lower().split() for w in ("two", "three", "four")))
                if kind == "quantity":
                    check_old = count(old) if old > 1 else ""
                    check_new = count(new) if new > 1 else ""
                else:
                    check_old, check_new = old_w, new_w
                if quantity_ok and self._check(text, candidate, check_old, check_new):
                    change(line)
                    return candidate, gold, f"{kind}:{old}->{new}"
        return None


def build(menu_payload, hints, seeds_path, out_dir, log=print):
    rng = random.Random(2026)
    full = Menu(menu_payload, hints)
    by_name = Counter(i["name"].lower() for i in full.items)
    general_payload = dict(menu_payload, items=[i for i in menu_payload["items"] if by_name[i["name"].lower()] < 2])
    general = Menu(general_payload, hints)
    vocab, _ = paraphrase.menu_vocabulary(menu_payload, hints, LOCATIONS)
    vocab |= {paraphrase._stem(w) for w in ("pizza", "pie", "pies", "slice", "soda", "drink")}

    seeds = [json.loads(line) for line in open(seeds_path, encoding="utf-8")]
    order = list(range(len(seeds)))
    rng.shuffle(order)
    pools, start = {}, 0
    for split, share in SEED_SHARES.items():
        pools[split] = [seeds[i] for i in order[start:start + share]]
        start += share
    (out_dir / "seed_split.json").write_text(json.dumps(
        {split: [s["source_group"] for s in pool] for split, pool in pools.items()}, indent=1) + "\n", encoding="utf-8")

    editor = SeedEditor(menu_payload, vocab, rng)
    stats = Counter()
    all_rows = {}
    for split, size in SPLIT_SIZES.items():
        template_split = "test" if split == "test" else "dev"
        builder = V3Builder(general, full, template_split, rng)
        base, extra = divmod(size, len(CATEGORIES))
        quotas = {c: base + (1 if i < extra else 0) for i, c in enumerate(CATEGORIES)}
        pool = pools[split][:]
        rng.shuffle(pool)
        next_seed = [0]

        def take_seed():
            seed = pool[next_seed[0] % len(pool)]
            next_seed[0] += 1
            return seed

        rows, seen = [], set()
        for category in CATEGORIES:
            made, attempts = 0, 0
            while made < quotas[category] and attempts < quotas[category] * 40:
                attempts += 1
                seed = take_seed()
                if category == "pizza_seed":
                    result = editor.make(seed)
                    if result is None:
                        stats["pizza_seed_failed"] += 1
                        continue
                    text, gold, change = result
                    loc = rng.choice(LOCATIONS)
                    gold["delivery_location"] = loc
                    row = {"category": "pizza_seed", "template_id": f"pizza_seed:{change.split(':')[0]}",
                           "initial_utterance": f"{text}, deliver to {loc}", "clarification_replies": [],
                           "gold_order": gold, "seed_change": change}
                    for reply in seed["clarification_replies"]:
                        if reply.lower().startswith(("deliver it to", "to ")):
                            row["initial_utterance"] = text
                            row["clarification_replies"].append(f"Deliver it to {loc}." if reply.startswith("Deliver") else f"To {loc}, please.")
                        else:
                            row["clarification_replies"].append(reply)
                    row["restyled"] = False
                else:
                    method = "same_name_dialogue" if category == "same_name" else category
                    row = getattr(builder, method)()
                    if row is None:
                        break
                    original = row["initial_utterance"]
                    row["restyled"] = False
                    for attempt in range(2):
                        candidate = chat(STYLE_PROMPT.format(seed=seed_text(seed), text=original), seed=rng.randrange(1 << 30))
                        if plain(candidate) and paraphrase.acceptable(original, candidate, vocab, LOCATIONS):
                            row["initial_utterance"] = candidate
                            row["restyled"] = True
                            break
                    stats["restyle_tried"] += 1
                    stats["restyle_kept"] += row["restyled"]
                if row["initial_utterance"] in seen:
                    continue
                seen.add(row["initial_utterance"])
                row["source_group"] = seed["source_group"]
                row["style_seed"] = seed["source_group"]
                row["split"] = split
                rows.append(row)
                made += 1
                if made % 10 == 0:
                    log(f"  [{split}] {category}: {made}/{quotas[category]} after {attempts} attempts")
            stats[f"{split}:{category}"] = made
            log(f"[{split}] {category}: {made}/{quotas[category]}  ({dict((k, v) for k, v in stats.items() if 'restyle' in k)})")
        prefix = {"train": "v3-tr", "validation": "v3-va", "test": "v3-te"}[split]
        for index, row in enumerate(rows, start=1):
            row["dialogue_id"] = f"{prefix}-{index:04d}"
        all_rows[split] = rows
    return all_rows, stats, pools
