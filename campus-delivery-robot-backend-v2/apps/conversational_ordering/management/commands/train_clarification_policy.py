import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from apps.conversational_ordering.policies import FEATURE_NAMES


def read_rows(path, configuration):
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON on line {line_number}: {exc}") from exc
        features = row.get("features", row)
        try:
            vector = [float(features[name]) for name in FEATURE_NAMES]
            label = int(bool(row["wrong"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError(
                f"Each row needs numeric s1-s7 features and a boolean 'wrong' label (line {line_number})."
            ) from exc
        if configuration and row.get("configuration") != configuration:
            continue
        rows.append((vector, label))
    return rows


def clarification_rates(labels, ask):
    labels = np.asarray(labels, dtype=int)
    ask = np.asarray(ask, dtype=bool)
    wrong = labels == 1
    correct = ~wrong
    missed = float(np.mean(~ask[wrong])) if np.any(wrong) else 0.0
    unnecessary = float(np.mean(ask[correct])) if np.any(correct) else 0.0
    return missed, unnecessary


class Command(BaseCommand):
    help = "Train and calibrate the C5 wrong-draft classifier; select its question threshold on validation data."

    def add_arguments(self, parser):
        parser.add_argument("--train", required=True, help="Training per-turn feature JSONL")
        parser.add_argument("--validation", required=True, help="Validation per-turn feature JSONL")
        parser.add_argument("--output", default=str(settings.AI_POLICY_MODEL_PATH))
        parser.add_argument("--configuration", default="C2", help="Use only feature rows from this policy run")
        parser.add_argument("--missed-cost", type=float, default=5.0)
        parser.add_argument("--unnecessary-cost", type=float, default=1.0)

    def handle(self, *args, **options):
        train_rows = read_rows(options["train"], options["configuration"])
        validation_rows = read_rows(options["validation"], options["configuration"])
        if not train_rows or not validation_rows:
            raise CommandError("Training and validation files must both contain rows.")
        train_x = np.asarray([row[0] for row in train_rows], dtype=float)
        train_y = np.asarray([row[1] for row in train_rows], dtype=int)
        validation_x = np.asarray([row[0] for row in validation_rows], dtype=float)
        validation_y = np.asarray([row[1] for row in validation_rows], dtype=int)
        class_counts = np.bincount(train_y, minlength=2)
        if class_counts.min() < 2:
            raise CommandError("Training data needs at least two examples of both correct and wrong drafts.")

        cv = min(5, int(class_counts.min()))
        base = make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42),
        )
        classifier = CalibratedClassifierCV(
            estimator=base, method="sigmoid", cv=cv
        ).fit(train_x, train_y)
        probabilities = classifier.predict_proba(validation_x)[:, 1]
        thresholds = np.unique(np.concatenate(([0.0, 1.0], probabilities)))
        best = None
        for threshold in thresholds:
            ask = probabilities >= threshold
            missed, unnecessary = clarification_rates(validation_y, ask)
            cost = options["missed_cost"] * missed + options["unnecessary_cost"] * unnecessary
            candidate = (cost, float(threshold), missed, unnecessary)
            if best is None or candidate < best:
                best = candidate

        output = Path(options["output"])
        if output.exists():
            raise CommandError(
                f"Refusing to overwrite existing model artifact: {output}. Choose a new --output path."
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        auc = float(roc_auc_score(validation_y, probabilities)) if len(set(validation_y)) > 1 else None
        bundle = {
            "classifier": classifier,
            "threshold": best[1],
            "feature_names": list(FEATURE_NAMES),
            "model_card": {
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "train_rows": len(train_rows),
                "validation_rows": len(validation_rows),
                "missed_cost": options["missed_cost"],
                "unnecessary_cost": options["unnecessary_cost"],
                "validation_missed_rate": best[2],
                "validation_unnecessary_rate": best[3],
                "validation_brier_score": float(brier_score_loss(validation_y, probabilities)),
                "validation_auroc": auc,
            },
        }
        joblib.dump(bundle, output)
        self.stdout.write(
            self.style.SUCCESS(
                f"Saved C5 model to {output}; threshold={best[1]:.4f}, "
                f"validation AUROC={auc if auc is not None else 'n/a'}"
            )
        )
