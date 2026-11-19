"""Build dataset v2 end to end with fixed seeds.

    python build_v2.py            # needs Ollama with qwen3.5:9b for paraphrasing
    python build_v2.py --no-paraphrase

Writes (relative to this folder):
    splits/train.jsonl, splits/validation.jsonl   menu A (v1 menu), dev templates
    splits/test_a.jsonl                           menu A, test templates only
    splits/test_b.jsonl                           held-out menu B, test templates only
    ../external/pizza_human.jsonl                 PIZZA human-written orders on menu B (git-ignored)
    manifest.json                                 counts and paraphrase rates
"""

import argparse
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import paraphrase  # noqa: E402
from generate_v2 import LOCATIONS, Menu, generate  # noqa: E402

FIELDS = ["dialogue_id", "category", "source_group", "template_id", "initial_utterance",
          "clarification_replies", "reply_kind", "paraphrased", "gold_order"]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({k: row[k] for k in FIELDS if k in row}, ensure_ascii=False) + "\n")


def stratified_split(rows, share, rng):
    by_category = {}
    for row in rows:
        by_category.setdefault(row["category"], []).append(row)
    first, second = [], []
    for category in sorted(by_category):
        group = by_category[category][:]
        rng.shuffle(group)
        cut = round(len(group) * share)
        first += group[:cut]
        second += group[cut:]
    return first, second


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-paraphrase", action="store_true")
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--share", type=float, default=0.5)
    args = parser.parse_args()

    subprocess.run([sys.executable, str(HERE / "make_menu_b.py"), str(HERE / "menu_snapshot_b.json")], check=True)
    menu_a_payload = load(HERE.parent / "menu_snapshot_v1.json")
    menu_b_payload = load(HERE / "menu_snapshot_b.json")
    hints_a = load(HERE / "hints_menu_a.json")
    hints_b = load(HERE / "hints_menu_b.json")
    menu_a = Menu(menu_a_payload, hints_a)
    menu_b = Menu(menu_b_payload, hints_b)

    dev = generate(menu_a, "dev", 89, seed=7, prefix="a-dev")
    train, validation = stratified_split(dev, 0.75, random.Random(17))
    sets = {
        "train": (train, menu_a_payload, hints_a),
        "validation": (validation, menu_a_payload, hints_a),
        "test_a": (generate(menu_a, "test", 22, seed=8, prefix="a-test"), menu_a_payload, hints_a),
        "test_b": (generate(menu_b, "test", 20, seed=9, prefix="b-test"), menu_b_payload, hints_b),
    }

    raw = HERE.parent / "external" / "raw"
    pizza_out = HERE.parent / "external" / "pizza_human.jsonl"
    if (raw / "PIZZA_test.json").exists():
        subprocess.run([sys.executable, str(HERE / "convert_pizza.py"), str(raw / "PIZZA_test.json"),
                        str(raw / "PIZZA_dev.json"), "--out", str(pizza_out), "--sample", "300"], check=True)
    else:
        print("PIZZA downloads not found; skipping pizza_human.jsonl (see SOURCES.md)")

    manifest = {}
    for offset, (name, (rows, payload, hints)) in enumerate(sets.items()):
        stats = {"tried": 0, "kept": 0}
        if not args.no_paraphrase:
            vocab, _ = paraphrase.menu_vocabulary(payload, hints, LOCATIONS)
            stats = paraphrase.paraphrase_rows(
                rows, args.model, vocab, LOCATIONS, random.Random(100 + offset), share=args.share,
                log=lambda msg, name=name: print(f"[{name}] {msg}", flush=True),
            )
        write(HERE / "splits" / f"{name}.jsonl", rows)
        manifest[name] = {
            "dialogues": len(rows),
            "categories": dict(sorted(Counter(r["category"] for r in rows).items())),
            "templates": len({r["template_id"] for r in rows}),
            "paraphrase_tried": stats["tried"],
            "paraphrase_kept": stats["kept"],
            "dialogues_with_paraphrase": sum(1 for r in rows if r.get("paraphrased")),
        }
        print(name, manifest[name], flush=True)
    dev_templates = {r["template_id"] for name in ("train", "validation") for r in sets[name][0]}
    test_templates = {r["template_id"] for name in ("test_a", "test_b") for r in sets[name][0]}
    manifest["template_overlap_dev_test"] = sorted(dev_templates & test_templates)
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("overlap", manifest["template_overlap_dev_test"])


if __name__ == "__main__":
    main()
