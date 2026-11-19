"""Dataset v2 generator: menu-driven, with disjoint dev and test templates.

Unlike data/generate_dialogues.py (v1), nothing here names a menu item. Item
families, option wording and unavailable requests all come from the menu
snapshot plus a small hints file, so the same code generates dialogues for any
vendor's menu:

    python generate_v2.py --menu menu.json --hints hints.json --split test \
        --per-category 20 --out test.jsonl

``--split dev`` uses only dev templates; ``--split test`` only test templates.
The test-template reply wording follows customer phrasings attested in
Taskmaster-1 (see SOURCES.md).
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

LOCATIONS = [
    "Sprague Library", "Student Center", "University Hall", "Blanton Hall",
    "Recreation Center", "Dickson Hall", "Calcia Hall", "Freeman Hall",
    "Richardson Hall", "Partridge Hall", "Life Hall", "College Hall",
]
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                7: "seven", 8: "eight", 9: "nine", 10: "ten"}
# Option groups whose choice is said before the item name ("a large cola").
BEFORE_GROUPS = {"size", "flavor", "protein", "filling"}
ABSENT_SIZES = ["Small", "Medium", "Large", "Extra large", "Regular", "Personal"]

# ---------------------------------------------------------------- templates
# Each category has dev templates (train/validation) and test templates. The two
# sets never share a template, so test sentences have wording that the
# assistant and C5 were not developed on.
T = {
    "clear_request": {
        "dev": [
            "I'd like {order}, delivered to {loc}.",
            "Can I get {order} to {loc}?",
            "{Order} to {loc}, please.",
            "Please send {order} to {loc}.",
            "I want {order}, deliver to {loc}.",
            "Could you bring {order} to {loc}?",
        ],
        "test": [
            "Hi, I'm at {loc}. Can you send {order}?",
            "Order for {loc}: {order}.",
            "Hey, could I grab {order}? I'm in {loc}.",
            "{loc}, please. {Order}.",
        ],
    },
    "ambiguous_item": {
        "dev": [
            "I'll have {vague}, deliver to {loc}.",
            "Can I get {vague} to {loc}?",
            "{Vague} to {loc}, please.",
        ],
        "test": [
            "I'm at {loc}, just want {vague}.",
            "Could you send {vague} over to {loc}?",
        ],
    },
    "unavailable_option": {
        "dev": ["{Request} to {loc}.", "Can I get {request} to {loc}?"],
        "test": ["I'm at {loc}, could I get {request}?", "{Request} for {loc}, please."],
    },
    "customization": {
        "dev": ["Could I get {order} delivered to {loc}?", "{Order} to {loc}."],
        "test": ["Send {order} my way, I'm at {loc}.", "Can {loc} get {order}?"],
    },
    "split_line": {
        "dev": ["Two {base}, one of them {extra}, deliver to {loc}."],
        "test": ["Two {base} to {loc}: one {extra} and one plain."],
    },
    "correction": {
        "dev": ["{Order} to {loc}.", "Please send {order} to {loc}.", "I want {order} sent to {loc}."],
        "test": ["Hi, {order} to {loc} please.", "Could {loc} get {order}?"],
    },
    "removal": {
        "dev": ["{Order} to {loc}.", "Can I get {order}, deliver to {loc}?"],
        "test": ["Hey, I'm at {loc}. {Order}, please."],
    },
    "multi_item": {
        "dev": ["I'd like {order}, delivered to {loc}.", "Can I get {order} to {loc}?"],
        "test": ["Order for {loc}: {order}.", "Hi, I'm at {loc}. Can you send {order}?"],
    },
    "multi_problem": {
        "dev": ["I'll have {order}, deliver to {loc}."],
        "test": ["Hey, I'm at {loc}. Just {order}."],
    },
    "quantity_limit": {
        "dev": ["{Order} to {loc}.", "Can I get {order} to {loc}?"],
        "test": ["We need {order} at {loc}."],
    },
    "partial_answer": {
        "dev": ["Could I get {order} delivered to {loc}?"],
        "test": ["Can {loc} get {order}?"],
    },
}
# Replies. Test wording follows Taskmaster-1 customer carriers ("make it a
# large", "let's go with", "on second thought", "instead of the", "wait, I want
# to change", short size answers like "large please.").
R = {
    "full": {"dev": ["{Order}.", "I'll go with {order}."], "test": ["Let's go with {order}.", "Make it {order}."]},
    "distinct": {"dev": ["The {distinct} one."], "test": ["Oh, the {distinct} one."]},
    "option": {"dev": ["{Option}.", "{Option}, please."], "test": ["{option} please.", "Let's do {option}."]},
    "alt": {"dev": ["{Alt} instead."], "test": ["Okay, {alt} then.", "On second thought, {alt}."]},
    "absent": {"dev": ["{Option} is fine."], "test": ["Hmm, {option} then."]},
    "quantity": {"dev": ["Actually, make that {n}."], "test": ["Wait, I want to change that to {n}.", "On second thought, make it {n}."]},
    "location": {"dev": ["Deliver it to {loc} instead."], "test": ["Sorry, send it to {loc} instead."]},
    "swap": {"dev": ["Change that to {order}."], "test": ["Instead of the {name}, can I get {order}?"]},
    "option_change": {"dev": ["Make it {option} instead."], "test": ["Let's make it {option}."]},
    "remove": {"dev": ["Actually, remove the {name}.", "Drop the {name}, please."], "test": ["Never mind the {name}.", "Scratch the {name}."]},
    "limit": {"dev": ["Okay, {n} then."], "test": ["Fine, make it {n}."]},
    "both": {"dev": ["{Order}."], "test": ["Let's go with {order}."]},
}


def cap(text):
    return text[:1].upper() + text[1:]


def fill(template, **values):
    out = template
    for key, value in values.items():
        out = out.replace("{" + cap(key) + "}", cap(str(value)))
        out = out.replace("{" + key + "}", str(value))
    return out


# ---------------------------------------------------------------- phrasing
class Menu:
    def __init__(self, payload, hints):
        self.payload = payload
        self.hints = hints
        self.items = [item for item in payload["items"] if item["available"]]
        self.unavailable = [item for item in payload["items"] if not item["available"]]
        self.by_id = {item["id"]: item for item in payload["items"]}
        self.by_vendor = {}
        for item in self.items:
            self.by_vendor.setdefault(item["vendor_id"], []).append(item)
        families = {}
        for item in self.items:
            families.setdefault(self.head(item), []).append(item)
        self.families = {
            word: members for word, members in families.items() if word and len(members) >= 2
        }

    def head(self, item):
        """The general word for an item ("burger"); a hint of "" keeps it out of every family."""
        hint = self.hints.get("items", {}).get(item["id"], {})
        if "family" in hint:
            return hint["family"]
        return item["name"].split()[-1].lower()

    def unit(self, item):
        return self.hints.get("items", {}).get(item["id"], {}).get("unit")

    def say_group(self, group):
        return self.hints.get("groups", {}).get(group["name"], {})


def article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def pluralize(name):
    words = name.split()
    last = words[-1]
    if last.endswith("s"):
        return name
    if re.search(r"(ch|sh|x)$", last):
        last += "es"
    elif re.search(r"[^aeiou]y$", last):
        last = last[:-1] + "ies"
    else:
        last += "s"
    return " ".join(words[:-1] + [last])


def count(n):
    return NUMBER_WORDS.get(n, str(n))


def is_before(menu, group):
    hint = menu.say_group(group)
    return bool(hint.get("before")) or (group["name"].lower() in BEFORE_GROUPS and "say" not in hint)


def option_text(menu, group, option):
    """How an option is said after the item name ("with ranch", "on wheat", "no onions")."""
    hint = menu.say_group(group)
    low = option.lower()
    if "say" in hint:
        return hint["say"].replace("{option}", low)
    if low.startswith("no "):
        return low
    return f"with {low}"


def phrase(menu, item, n, selected, with_count=True):
    """English phrase for ``n`` of ``item`` with ``selected`` [(group, option)]."""
    before, after = [], []
    for group, option in selected:
        if is_before(menu, group):
            before.append(option.lower())
        else:
            after.append(option_text(menu, group, option))
    name = item["name"].lower()
    unit = menu.unit(item)
    head = " ".join(before + [name])
    if unit:
        body = f"{unit} of {head}" if n == 1 else f"{count(n)} {unit}s of {head}"
        if n == 1 and with_count:
            body = f"{article(unit)} {body}"
    elif n == 1:
        body = f"{article(head)} {head}" if with_count else head
    else:
        body = f"{count(n)} {pluralize(head)}"
    joined = []
    for index, part in enumerate(after):
        if index == 0:
            joined.append(part)
        elif part.startswith("with "):
            joined.append("and " + part[len("with "):])
        else:
            joined.append(f"and {part}")
    return " ".join([body] + joined) if joined else body


def required_groups(item):
    return [g for g in item["option_groups"] if g["required"]]


def optional_groups(item):
    return [g for g in item["option_groups"] if not g["required"]]


def pick_required(rng, item):
    return [(g, rng.choice(g["options"])) for g in required_groups(item)]


def gold_line(item, n, selected):
    return {"menu_item_id": item["id"], "quantity": n, "customizations": [option for _, option in selected]}


def qty(rng, item, top=3):
    return rng.randint(1, max(1, min(top, item["max_quantity"])))


# ---------------------------------------------------------------- categories
class Builder:
    def __init__(self, menu, split, rng):
        self.menu, self.split, self.rng = menu, split, rng

    def tpl(self, category):
        options = T[category][self.split]
        index = self.rng.randrange(len(options))
        return f"{category}:{self.split}:{index}", options[index]

    def reply(self, kind, **values):
        options = R[kind][self.split]
        return fill(self.rng.choice(options), **values)

    def loc(self):
        return self.rng.choice(LOCATIONS)

    def dialogue(self, category, template_id, utterance, replies, vendor_id, location, lines, reply_kind=None):
        row = {
            "category": category,
            "template_id": template_id,
            "initial_utterance": utterance,
            "clarification_replies": replies,
            "gold_order": {"vendor_id": vendor_id, "delivery_location": location, "items": lines},
        }
        if reply_kind:
            row["reply_kind"] = reply_kind
        return row

    def any_item(self, need=None):
        pool = [item for item in self.menu.items if need is None or need(item)]
        return self.rng.choice(pool) if pool else None

    def full_order(self, item=None, n=None, optional=0.3):
        item = item or self.any_item()
        n = n or qty(self.rng, item)
        selected = pick_required(self.rng, item)
        groups = [g for g in optional_groups(item) if g["options"]]
        if groups and self.rng.random() < optional:
            group = self.rng.choice(groups)
            selected.append((group, self.rng.choice(group["options"])))
        return item, n, selected

    # 1
    def clear_request(self):
        item, n, selected = self.full_order()
        tid, t = self.tpl("clear_request")
        loc = self.loc()
        return self.dialogue("clear_request", tid, fill(t, order=phrase(self.menu, item, n, selected), loc=loc),
                             [], item["vendor_id"], loc, [gold_line(item, n, selected)])

    # 2
    def ambiguous_item(self):
        word = self.rng.choice(sorted(self.menu.families))
        members = self.menu.families[word]
        item = self.rng.choice(members)
        n = qty(self.rng, item, 2)
        selected = pick_required(self.rng, item)
        vague = f"{article(word)} {word}" if n == 1 else f"{count(n)} {pluralize(word)}"
        tid, t = self.tpl("ambiguous_item")
        loc = self.loc()
        distinct = " ".join(w for w in item["name"].lower().split() if w not in word.split()) or None
        others_share = distinct and sum(distinct in m["name"].lower() for m in members) > 1
        if distinct and not others_share and self.rng.random() < 0.5:
            replies = [self.reply("distinct", distinct=distinct)]
            if selected:
                replies.append(self.reply("option", option=" and ".join(o.lower() for _, o in selected)))
        else:
            replies = [self.reply("full", order=phrase(self.menu, item, n, selected))]
        return self.dialogue("ambiguous_item", tid, fill(t, vague=vague, loc=loc), replies,
                             item["vendor_id"], loc, [gold_line(item, n, selected)])

    # 3
    def unavailable_option(self):
        tid, t = self.tpl("unavailable_option")
        loc = self.loc()
        kinds = ["absent"]
        if self.menu.unavailable:
            kinds.append("item")
        if self.menu.hints.get("off_menu"):
            kinds.append("off_menu")
        kind = self.rng.choice(kinds)
        if kind == "absent":
            # An option the item does not offer, from the same group elsewhere on the menu.
            candidates = []
            for item in self.menu.items:
                for group in required_groups(item):
                    seen = {o for other in self.menu.items for g in other["option_groups"]
                            if g["name"] == group["name"] for o in g["options"]}
                    if group["name"].lower() == "size":
                        seen |= set(ABSENT_SIZES)
                    missing = sorted(seen - set(group["options"]))
                    for option in missing:
                        candidates.append((item, group, option))
            item, group, absent = self.rng.choice(candidates)
            choice = self.rng.choice(group["options"])
            chosen = pick_required(self.rng, item)
            request = phrase(self.menu, item, 1, [(g, absent if g is group else o) for g, o in chosen])
            real = [(g, choice if g is group else o) for g, o in chosen]
            reply = self.reply("absent", option=choice.lower())
            return self.dialogue("unavailable_option", tid, fill(t, request=request, loc=loc), [reply],
                                 item["vendor_id"], loc, [gold_line(item, 1, real)])
        if kind == "item":
            missing = self.rng.choice(self.menu.unavailable)
            request = phrase(self.menu, missing, 1, [])
            vendor_id = missing["vendor_id"]
        else:
            entry = self.rng.choice(self.menu.hints["off_menu"])
            request, vendor_id = entry["request"], entry["vendor_id"]
        alt, n, selected = self.full_order(self.rng.choice(self.menu.by_vendor[vendor_id]), 1, optional=0)
        reply = self.reply("alt", alt=phrase(self.menu, alt, 1, selected))
        return self.dialogue("unavailable_option", tid, fill(t, request=request, loc=loc), [reply],
                             vendor_id, loc, [gold_line(alt, 1, selected)])

    # 4
    def customization(self):
        if self.rng.random() < 0.3:
            return self.split_line()
        item = self.any_item(lambda i: len(required_groups(i)) == 1)
        n = qty(self.rng, item, 2)
        selected = pick_required(self.rng, item)
        tid, t = self.tpl("customization")
        loc = self.loc()
        reply = self.reply("option", option=" and ".join(o.lower() for _, o in selected))
        return self.dialogue("customization", tid, fill(t, order=phrase(self.menu, item, n, []), loc=loc), [reply],
                             item["vendor_id"], loc, [gold_line(item, n, selected)])

    def split_line(self):
        item = self.any_item(lambda i: any(g["max_selections"] >= 1 and g["options"] for g in optional_groups(i))
                             and i["max_quantity"] >= 2)
        selected = pick_required(self.rng, item)
        group = self.rng.choice([g for g in optional_groups(item) if g["options"]])
        option = self.rng.choice(group["options"])
        base = phrase(self.menu, item, 2, selected)[len("two "):]
        tid, t = self.tpl("split_line")
        loc = self.loc()
        lines = [gold_line(item, 1, selected), gold_line(item, 1, selected + [(group, option)])]
        utterance = fill(t, base=base, extra=option_text(self.menu, group, option), loc=loc)
        return self.dialogue("customization", tid, utterance, [], item["vendor_id"], loc, lines)

    # 5
    def correction(self):
        tid, t = self.tpl("correction")
        loc = self.loc()
        item, n, selected = self.full_order(n=1, optional=0)
        utterance = fill(t, order=phrase(self.menu, item, 1, selected), loc=loc)
        kind = self.rng.choice(["quantity", "location", "swap", "option_change"])
        if kind == "option_change":
            changeable = [g for g, _ in selected if len(g["options"]) > 1]
            if not changeable:
                kind = "quantity"
        if kind == "quantity":
            new_n = self.rng.randint(2, min(3, item["max_quantity"]))
            return self.dialogue("correction", tid, utterance, [self.reply("quantity", n=count(new_n))],
                                 item["vendor_id"], loc, [gold_line(item, new_n, selected)], "correction")
        if kind == "location":
            new_loc = self.rng.choice([l for l in LOCATIONS if l != loc])
            return self.dialogue("correction", tid, utterance, [self.reply("location", loc=new_loc)],
                                 item["vendor_id"], new_loc, [gold_line(item, 1, selected)], "correction")
        if kind == "swap":
            others = [i for i in self.menu.by_vendor[item["vendor_id"]] if i["id"] != item["id"]]
            if others:
                target, n2, sel2 = self.full_order(self.rng.choice(others), optional=0)
                reply = self.reply("swap", order=phrase(self.menu, target, n2, sel2), name=item["name"].lower())
                return self.dialogue("correction", tid, utterance, [reply], item["vendor_id"], loc,
                                     [gold_line(target, n2, sel2)], "correction")
            kind = "option_change"
        group = self.rng.choice([g for g, _ in selected if len(g["options"]) > 1])
        current = dict((g["name"], o) for g, o in selected)[group["name"]]
        new = self.rng.choice([o for o in group["options"] if o != current])
        changed = [(g, new if g["name"] == group["name"] else o) for g, o in selected]
        return self.dialogue("correction", tid, utterance, [self.reply("option_change", option=new.lower())],
                             item["vendor_id"], loc, [gold_line(item, 1, changed)], "correction")

    def _two_items(self):
        vendor = self.rng.choice([v for v, items in self.menu.by_vendor.items() if len(items) >= 2])
        first, second = self.rng.sample(self.menu.by_vendor[vendor], 2)
        return vendor, first, second

    # 6
    def removal(self):
        vendor, first, second = self._two_items()
        a = self.full_order(first, optional=0)
        b = self.full_order(second, optional=0)
        order = f"{phrase(self.menu, *a)} and {phrase(self.menu, *b)}"
        tid, t = self.tpl("removal")
        loc = self.loc()
        reply = self.reply("remove", name=second["name"].lower())
        return self.dialogue("removal", tid, fill(t, order=order, loc=loc), [reply], vendor, loc,
                             [gold_line(*a)], "correction")

    # 7
    def multi_item(self):
        vendor = self.rng.choice([v for v, items in self.menu.by_vendor.items() if len(items) >= 3])
        count_items = self.rng.choice([2, 2, 3])
        picks = [self.full_order(item) for item in self.rng.sample(self.menu.by_vendor[vendor], count_items)]
        parts = [phrase(self.menu, *p) for p in picks]
        order = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        tid, t = self.tpl("multi_item")
        loc = self.loc()
        return self.dialogue("multi_item", tid, fill(t, order=order, loc=loc), [], vendor, loc,
                             [gold_line(*p) for p in picks])

    # 8
    def multi_problem(self):
        # One vague item and one item missing a required option, same vendor.
        choices = []
        for word, members in self.menu.families.items():
            vendor = members[0]["vendor_id"]
            if any(m["vendor_id"] != vendor for m in members):
                continue
            others = [i for i in self.menu.by_vendor[vendor] if i not in members and len(required_groups(i)) == 1]
            if others:
                choices.append((word, members, others))
        if not choices:
            return self.customization()
        word, members, others = self.rng.choice(choices)
        first = self.rng.choice(members)
        second = self.rng.choice(others)
        a = (first, 1, pick_required(self.rng, first))
        b = (second, 1, pick_required(self.rng, second))
        order = f"{article(word)} {word} and {phrase(self.menu, second, 1, [])}"
        tid, t = self.tpl("multi_problem")
        loc = self.loc()
        reply = self.reply("both", order=f"{phrase(self.menu, *a)} and {phrase(self.menu, *b)}")
        return self.dialogue("multi_problem", tid, fill(t, order=order, loc=loc), [reply],
                             first["vendor_id"], loc, [gold_line(*a), gold_line(*b)])

    # 9
    def quantity_limit(self):
        item = self.any_item()
        over = item["max_quantity"] + self.rng.randint(1, 6)
        selected = pick_required(self.rng, item)
        tid, t = self.tpl("quantity_limit")
        loc = self.loc()
        reply = self.reply("limit", n=count(item["max_quantity"]))
        return self.dialogue("quantity_limit", tid, fill(t, order=phrase(self.menu, item, over, selected), loc=loc),
                             [reply], item["vendor_id"], loc, [gold_line(item, item["max_quantity"], selected)])

    # 10
    def partial_answer(self):
        item = self.any_item(lambda i: len(required_groups(i)) >= 2)
        if item is None:
            return None
        n = qty(self.rng, item, 2)
        selected = pick_required(self.rng, item)
        tid, t = self.tpl("partial_answer")
        loc = self.loc()
        replies = [self.reply("option", option=o.lower()) for _, o in selected]
        return self.dialogue("partial_answer", tid, fill(t, order=phrase(self.menu, item, n, []), loc=loc), replies,
                             item["vendor_id"], loc, [gold_line(item, n, selected)])


CATEGORIES = ["clear_request", "ambiguous_item", "unavailable_option", "customization", "correction",
              "removal", "multi_item", "multi_problem", "quantity_limit", "partial_answer"]


def generate(menu, split, per_category, seed, prefix):
    rng = random.Random(seed)
    builder = Builder(menu, split, rng)
    rows, seen = [], set()
    for category in CATEGORIES:
        made, attempts = 0, 0
        while made < per_category and attempts < per_category * 60:
            attempts += 1
            row = getattr(builder, category)()
            if row is None:
                break
            if row["initial_utterance"] in seen:
                continue
            seen.add(row["initial_utterance"])
            row["dialogue_id"] = f"{prefix}-{len(rows) + 1:04d}"
            # Each dialogue is its own group; the template split is what keeps
            # test wording unseen (template_id records it).
            row["source_group"] = row["dialogue_id"]
            rows.append(row)
            made += 1
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--menu", required=True)
    parser.add_argument("--hints", required=True)
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--per-category", type=int, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.menu).read_text(encoding="utf-8"))
    hints = json.loads(Path(args.hints).read_text(encoding="utf-8"))
    rows = generate(Menu(payload, hints), args.split, args.per_category, args.seed, args.prefix)
    order = ["dialogue_id", "category", "source_group", "template_id", "initial_utterance",
             "clarification_replies", "reply_kind", "gold_order"]
    with open(args.out, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({k: row[k] for k in order if k in row}, ensure_ascii=False) + "\n")
    counts = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    print(args.out, len(rows), counts)


if __name__ == "__main__":
    main()
