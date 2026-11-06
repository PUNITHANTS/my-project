import json
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sklearn.metrics import brier_score_loss, roc_auc_score


def expected_calibration_error(labels, probabilities, bins=10):
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    total = len(labels)
    error = 0.0
    for lower in np.linspace(0, 1, bins, endpoint=False):
        upper = lower + 1 / bins
        mask = (probabilities >= lower) & (probabilities < upper if upper < 1 else probabilities <= upper)
        if np.any(mask):
            error += np.mean(mask) * abs(np.mean(probabilities[mask]) - np.mean(labels[mask]))
    return float(error) if total else None


class Command(BaseCommand):
    help = "Replay C1-C5 clarification decisions from annotated per-turn feature JSONL."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Held-out test feature JSONL")
        parser.add_argument("--output", help="Optional JSON summary output path")
        parser.add_argument("--confidence-threshold", type=float, default=settings.AI_CONFIDENCE_THRESHOLD)

    def handle(self, *args, **options):
        rows = []
        for line_number, line in enumerate(Path(options["input"]).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                features = row.get("features", row)
                signals = {f"s{i}": float(features[f"s{i}"]) for i in range(1, 8)}
                wrong = int(bool(row["wrong"]))
                model_requested = bool(row.get("model_requested_clarification", signals["s7"]))
                violation = bool(row.get("validation_violation", False))
                missing = float(row.get("missing_required_count", signals["s4"]))
                near_matches = float(row.get("near_match_count", signals["s3"]))
                dialogue_id = str(row.get("dialogue_id", line_number))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise CommandError(f"Invalid feature row on line {line_number}: {exc}") from exc
            rows.append((signals, wrong, model_requested, violation, missing, near_matches, dialogue_id))
        if not rows:
            raise CommandError("The test file contains no rows.")

        try:
            bundle = joblib.load(settings.AI_POLICY_MODEL_PATH)
            classifier = bundle["classifier"]
            c5_threshold = float(bundle["threshold"])
            features = np.asarray([[row[0][f"s{i}"] for i in range(1, 8)] for row in rows])
            c5_probabilities = classifier.predict_proba(features)[:, 1]
        except (OSError, KeyError, ValueError):
            classifier = None
            c5_threshold = options["confidence_threshold"]
            c5_probabilities = None

        labels = np.asarray([row[1] for row in rows], dtype=int)
        decisions = {name: [] for name in ("C1", "C2", "C3", "C4", "C5")}
        per_dialogue = {name: defaultdict(int) for name in decisions}
        for index, (signals, wrong, model_requested, violation, missing, near_matches, dialogue_id) in enumerate(rows):
            decisions["C1"].append(model_requested)
            decisions["C2"].append(violation or model_requested)
            decisions["C3"].append(violation or missing > 0 or near_matches >= 2)
            decisions["C4"].append(violation or missing > 0 or signals["s1"] < options["confidence_threshold"])
            c5_ask = (
                violation or missing > 0 or
                (c5_probabilities[index] >= c5_threshold if classifier else missing > 0 or near_matches >= 2)
            )
            decisions["C5"].append(bool(c5_ask))
            for name in decisions:
                per_dialogue[name][dialogue_id] += int(decisions[name][-1])

        summary = {}
        for name, ask in decisions.items():
            ask_array = np.asarray(ask, dtype=bool)
            wrong_mask = labels == 1
            correct_mask = ~wrong_mask
            summary[name] = {
                "turns": len(rows),
                "missed_clarification_rate": float(np.mean(~ask_array[wrong_mask])) if np.any(wrong_mask) else None,
                "unnecessary_clarification_rate": float(np.mean(ask_array[correct_mask])) if np.any(correct_mask) else None,
                "questions_per_dialogue": float(np.mean(list(per_dialogue[name].values()))),
            }

        if c5_probabilities is not None:
            summary["C5"]["brier_score"] = float(brier_score_loss(labels, c5_probabilities))
            summary["C5"]["expected_calibration_error"] = expected_calibration_error(labels, c5_probabilities)
            summary["C5"]["auroc"] = float(roc_auc_score(labels, c5_probabilities)) if len(set(labels)) > 1 else None
        else:
            summary["C5"]["note"] = "C5 artifact missing; C3 rule fallback was evaluated."

        rendered = json.dumps(summary, indent=2)
        if options["output"]:
            output = Path(options["output"])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
        self.stdout.write(rendered)
