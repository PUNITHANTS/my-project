"""Build dataset v3 end to end (needs Ollama with qwen3.5:9b), then check and export it.

    python data/v3/build_v3.py            # from delivery-robot/backend

Writes (in data/v3/):
    menu_snapshot_v3.json            frozen menu
    seed_split.json                  which Seed-P orders seeded which split
    dialogues.jsonl                  all 1000 dialogues (field ``split``)
    splits/train.jsonl, splits/validation.jsonl, splits/test.jsonl
    dialogues_v3.docx                plain-English copy in the format of the v1 document
    manifest.json                    counts, restyle rates, gold check, leakage check
"""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BACKEND))

FIELDS = ["dialogue_id", "split", "category", "source_group", "style_seed", "template_id",
          "initial_utterance", "clarification_replies", "reply_kind", "restyled", "seed_change", "gold_order"]
CATEGORY_LABELS = {
    "clear_request": ("Clear requests", "Clear request"),
    "ambiguous_item": ("Ambiguous items", "Ambiguous item"),
    "unavailable_option": ("Unavailable options", "Unavailable option"),
    "customization": ("Customizations", "Customization"),
    "correction": ("Corrections", "Correction"),
    "removal": ("Removals", "Removal"),
    "multi_item": ("Several items", "Several items"),
    "multi_problem": ("Several problems", "Several problems"),
    "quantity_limit": ("Quantity limits", "Quantity limit"),
    "partial_answer": ("Two missing options", "Two missing options"),
    "same_name": ("Same item at two restaurants", "Same item at two restaurants"),
    "pizza_seed": ("Edited human pizza orders", "Edited human pizza order"),
}
SPLIT_TITLES = {"train": "Train", "validation": "Validation", "test": "Test"}


def gold_problems(rows, catalog):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["AI_EXPERIMENT_MODE"] = "True"
    import django

    django.setup()
    from apps.conversational_ordering.menu_validation import validate_draft
    from apps.conversational_ordering.schemas import ParsedOrder

    problems = []
    for row in rows:
        gold = row["gold_order"]
        parsed = ParsedOrder.model_validate({
            "items": [{"menu_item_id": i["menu_item_id"], "mention": "", "quantity": i["quantity"],
                       "customizations": i["customizations"],
                       "confidence": {"item": 1, "quantity": 1, "customization": 1}} for i in gold["items"]],
            "delivery_location": gold["delivery_location"], "confidence": 1,
            "delivery_location_confidence": 1, "clarification_needed": None,
        })
        ids = {i["menu_item_id"] for i in gold["items"]}
        result = validate_draft(parsed, catalog, 0.65, resolved_item_ids=ids)
        found = [v["code"] for v in result["violations"]] + [m["kind"] for m in result["missing_details"]]
        vendors = {next(c["vendor_id"] for c in catalog if c["id"] == i) for i in ids}
        if vendors != {gold["vendor_id"]}:
            found.append("vendor_mismatch")
        if found:
            problems.append((row["dialogue_id"], row["category"], found))
    return problems


def gold_text(gold, by_id):
    parts = []
    for line in gold["items"]:
        item = by_id[line["menu_item_id"]]
        options = f" ({', '.join(line['customizations'])})" if line["customizations"] else ""
        parts.append(f"{line['quantity']} \u00d7 {item['name']}{options}")
    vendor = by_id[gold["items"][0]["menu_item_id"]]["vendor"]
    return f"{'; '.join(parts)}. {vendor}, deliver to {gold['delivery_location']}."


def menu_line(item):
    head = f"{item['name']} \u2014 ${item['price']}."
    if not item["available"]:
        head += " Unavailable."
    head += f" Maximum quantity {item['max_quantity']}."
    if not item["option_groups"]:
        return head + " No options."
    groups = "; ".join(
        f"{g['name']} ({'required' if g['required'] else 'optional'}): {', '.join(g['options'])}"
        for g in item["option_groups"])
    return f"{head} Options: {groups}."


def paragraph(text, style=None):
    style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{style_xml}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def export_docx(template, out, menu, splits, external_count):
    by_id = {item["id"]: item for item in menu["items"]}
    total = sum(len(rows) for rows in splits.values())
    body = [
        paragraph("Campus menu and annotated orders (dataset v3)", "Title"),
        paragraph(
            f"This file is a plain-English copy of the frozen menu (menu_snapshot_v3.json) and {total:,} "
            "annotated ordering dialogues, grouped by split. The gold order is the order the customer "
            "actually wants after any clarification or correction. It is the answer key, not the order the "
            "model produced."),
        paragraph(
            "Each dialogue was built from one human-written order of the PIZZA dataset (Seed-P), and all "
            "dialogues from one seed are in the same split. Edited human pizza orders keep that customer's "
            "own words with one detail changed. Other dialogues follow the menu and are rewritten in the "
            f"seed customer's style. The {external_count} External-P orders are held out and not listed here."),
        paragraph("Menu snapshot", "Heading1"),
        paragraph(
            "Synthetic campus menu used for these dialogues. It is not an export from the live database. "
            "Items marked unavailable are on the menu so the assistant can be asked for something it must "
            "refuse. Four items are sold under the same name by two restaurants, so the assistant has to ask "
            "which one."),
    ]
    for vendor in menu["vendors"]:
        body.append(paragraph(f"{vendor['name']} ({vendor['location_label']})", "Heading2"))
        body += [paragraph(menu_line(i), "ListBullet") for i in menu["items"] if i["vendor_id"] == vendor["id"]]
    body.append(paragraph("Annotated dialogues", "Heading1"))
    number = 0
    for split, rows in splits.items():
        body.append(paragraph(f"{SPLIT_TITLES[split]} ({len(rows)} dialogues)", "Heading1"))
        for category, (plural, singular) in CATEGORY_LABELS.items():
            chosen = [r for r in rows if r["category"] == category]
            if not chosen:
                continue
            body.append(paragraph(plural, "Heading2"))
            for row in chosen:
                number += 1
                body.append(paragraph(f"{number}. {singular}"))
                body.append(paragraph(f"Customer: {row['initial_utterance']}"))
                replies = row["clarification_replies"]
                body.append(paragraph(f"If asked: {replies[0] if replies else 'None.'}"))
                for reply in replies[1:]:
                    body.append(paragraph(f"If asked again: {reply}"))
                body.append(paragraph(f"Gold: {gold_text(row['gold_order'], by_id)}"))
    with zipfile.ZipFile(template) as source:
        document = source.read("word/document.xml").decode("utf-8")
        head = document[: document.index("<w:body>") + len("<w:body>")]
        tail = document[document.index("<w:sectPr"):]
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                if info.filename == "docProps/thumbnail.jpeg":
                    continue
                data = source.read(info.filename)
                if info.filename == "word/document.xml":
                    data = (head + "".join(body) + tail).encode("utf-8")
                elif info.filename == "_rels/.rels":
                    import re
                    data = re.sub(rb'<Relationship [^>]*thumbnail[^>]*/>', b"", data)
                elif info.filename == "[Content_Types].xml":
                    data = data.replace(b'<Default Extension="jpeg" ContentType="image/jpeg"/>', b"")
                target.writestr(info, data)


def main():
    subprocess.run([sys.executable, str(HERE / "make_menu_v3.py")], check=True)
    from generate_v3 import build

    menu = json.loads((HERE / "menu_snapshot_v3.json").read_text(encoding="utf-8"))
    hints = json.loads((HERE / "hints_menu_v3.json").read_text(encoding="utf-8"))
    seeds = BACKEND / "data" / "external" / "pizza_human.jsonl"
    external = BACKEND / "data" / "external" / "pizza_external_p.jsonl"
    splits, stats, pools = build(menu, hints, seeds, HERE, log=lambda m: print(m, flush=True))

    rows = [row for split in splits.values() for row in split]
    problems = gold_problems(rows, menu["items"])
    print("gold problems:", len(problems), problems[:10], flush=True)
    bad = {p[0] for p in problems}
    if bad:
        for split in splits:
            splits[split] = [r for r in splits[split] if r["dialogue_id"] not in bad]
        rows = [row for split in splits.values() for row in split]

    held_out = set(json.loads((HERE / "external_p_source_ids.json").read_text(encoding="utf-8"))["source_ids"])
    leaked = sorted({r["source_group"] for r in rows} & held_out)
    group_splits = {}
    for row in rows:
        group_splits.setdefault(row["source_group"], set()).add(row["split"])
    crossing = sorted(g for g, s in group_splits.items() if len(s) > 1)
    assert not leaked and not crossing, (leaked, crossing)

    (HERE / "splits").mkdir(exist_ok=True)
    with open(HERE / "dialogues.jsonl", "w", encoding="utf-8") as everything:
        for split, split_rows in splits.items():
            with open(HERE / "splits" / f"{split}.jsonl", "w", encoding="utf-8") as handle:
                for row in split_rows:
                    line = json.dumps({k: row[k] for k in FIELDS if k in row}, ensure_ascii=False) + "\n"
                    handle.write(line)
                    everything.write(line)

    external_count = sum(1 for _ in open(external, encoding="utf-8"))
    template = Path(os.environ.get("V3_DOCX_TEMPLATE", r"C:\Users\kamal\Downloads\Menu_Snapshot+Order_Prompts.docx"))
    if template.exists():
        export_docx(template, HERE / "dialogues_v3.docx", menu, splits, external_count)
    manifest = {
        "menu": {"vendors": len(menu["vendors"]), "items": len(menu["items"]),
                 "unavailable": sum(not i["available"] for i in menu["items"])},
        "seed_p": {split: len(pool) for split, pool in pools.items()},
        "external_p": external_count,
        "splits": {split: {"dialogues": len(r), "categories": dict(sorted(Counter(x["category"] for x in r).items())),
                           "restyled": sum(1 for x in r if x.get("restyled")),
                           "seeds_used": len({x["source_group"] for x in r})}
                   for split, r in splits.items()},
        "restyle": {"tried": stats["restyle_tried"], "kept": stats["restyle_kept"]},
        "pizza_seed_edit_failures": stats["pizza_seed_failed"],
        "gold_problems_dropped": [list(p) for p in problems],
        "external_p_seeds_used": leaked,
        "seed_groups_in_two_splits": crossing,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=1)[:2500])


if __name__ == "__main__":
    main()
