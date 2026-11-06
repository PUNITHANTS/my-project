import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


SPLITS = ("train", "validation", "test")
RATIOS = {"train": 0.6, "validation": 0.2, "test": 0.2}


def _read_jsonl(path):
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON on line {line_number}: {exc}") from exc
    return rows


class Command(BaseCommand):
    help = "Split annotated dialogues by source_group, approximating category-stratified 60/20/20 splits."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Raw JSONL with dialogue_id, category, source_group")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **options):
        rows = _read_jsonl(Path(options["input"]))
        if not rows:
            raise CommandError("The input dataset is empty.")
        groups = defaultdict(list)
        ids = set()
        for row in rows:
            for field in ("dialogue_id", "category", "source_group"):
                if not row.get(field):
                    raise CommandError(f"Every row needs {field!r}.")
            if row["dialogue_id"] in ids:
                raise CommandError(f"Duplicate dialogue_id: {row['dialogue_id']}")
            ids.add(row["dialogue_id"])
            groups[row["source_group"]].append(row)

        category_totals = Counter(row["category"] for row in rows)
        targets = {
            split: {category: count * RATIOS[split] for category, count in category_totals.items()}
            for split in SPLITS
        }
        assigned = {split: Counter() for split in SPLITS}
        rng = random.Random(options["seed"])
        group_items = list(groups.items())
        rng.shuffle(group_items)
        group_items.sort(key=lambda pair: len(pair[1]), reverse=True)
        output_rows = {split: [] for split in SPLITS}

        for _, group_rows in group_items:
            counts = Counter(row["category"] for row in group_rows)
            choices = []
            for split in SPLITS:
                score = 0.0
                for category, total in category_totals.items():
                    scale = max(1.0, targets[split][category])
                    delta = assigned[split][category] + counts[category] - targets[split][category]
                    score += (delta / scale) ** 2
                choices.append((score, rng.random(), split))
            split = min(choices)[2]
            output_rows[split].extend(group_rows)
            assigned[split].update(counts)

        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        targets = [output_dir / f"{split}.jsonl" for split in SPLITS]
        existing = [str(path) for path in targets if path.exists()]
        if existing:
            raise CommandError(
                "Refusing to overwrite existing split files: " + ", ".join(existing)
            )
        for split, split_rows in output_rows.items():
            path = output_dir / f"{split}.jsonl"
            path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in split_rows),
                encoding="utf-8",
            )
        for source_group, group_rows in groups.items():
            assigned_splits = {
                split
                for split, split_rows in output_rows.items()
                if any(row["source_group"] == source_group for row in split_rows)
            }
            if len(assigned_splits) != 1 or len(group_rows) == 0:
                raise CommandError(f"Source group {source_group!r} leaked across splits.")
        self.stdout.write(
            self.style.SUCCESS(
                "Wrote splits: " + ", ".join(f"{split}={len(output_rows[split])}" for split in SPLITS)
            )
        )
