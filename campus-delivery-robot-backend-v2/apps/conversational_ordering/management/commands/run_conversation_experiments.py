import json
import time
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.conversational_ordering.menu_validation import load_menu_catalog, normalize_text
from apps.conversational_ordering.services import parse_customer_turn
from apps.conversational_ordering.sessions import initial_session


POLICIES = ("C1", "C2", "C3", "C4", "C5")


def read_dialogues(path):
    dialogues = []
    seen = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON on line {line_number}: {exc}") from exc
        required = ("dialogue_id", "category", "source_group", "initial_utterance", "gold_order")
        if any(not row.get(field) for field in required):
            raise CommandError(
                f"Dialogue line {line_number} needs {', '.join(required)}."
            )
        if row["dialogue_id"] in seen:
            raise CommandError(f"Duplicate dialogue_id: {row['dialogue_id']}")
        if not isinstance(row.get("clarification_replies", []), list):
            raise CommandError(f"clarification_replies must be a list (line {line_number}).")
        gold = row["gold_order"]
        if not isinstance(gold.get("items"), list) or not gold.get("delivery_location"):
            raise CommandError(
                f"gold_order needs items and delivery_location (line {line_number})."
            )
        if not gold["items"]:
            raise CommandError(f"gold_order.items cannot be empty (line {line_number}).")
        seen.add(row["dialogue_id"])
        dialogues.append(row)
    if not dialogues:
        raise CommandError("The input file contains no dialogues.")
    return dialogues


def read_menu_snapshot(path):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        items = payload["items"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CommandError(f"Could not read a valid menu snapshot from {path}.") from exc
    if not isinstance(items, list) or not items:
        raise CommandError("The menu snapshot must contain a non-empty 'items' list.")
    return items


def _canonical_items(items, item_id_key):
    return sorted(
        (
            str(item.get(item_id_key) or ""),
            int(item.get("quantity", 0)),
            tuple(sorted(normalize_text(value) for value in item.get("customizations", []))),
        )
        for item in items
    )


def matches_gold(result, gold):
    if normalize_text(result.get("deliveryLocation")) != normalize_text(
        gold.get("delivery_location")
    ):
        return False
    if _canonical_items(result.get("items", []), "menuItemId") != _canonical_items(
        gold.get("items", []), "menu_item_id"
    ):
        return False
    expected_vendor = gold.get("vendor_id")
    return expected_vendor is None or str(result.get("vendorId")) == str(expected_vendor)


def _write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class Command(BaseCommand):
    help = "Replay annotated multi-turn dialogues against clarification policies C1-C5."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Dialogue JSONL for this dataset split")
        parser.add_argument("--output-dir", required=True)
        parser.add_argument("--menu-snapshot", help="Frozen catalog JSON produced by export_menu_snapshot")
        parser.add_argument("--max-turns", type=int, default=10)

    def handle(self, *args, **options):
        if options["max_turns"] < 1:
            raise CommandError("--max-turns must be at least 1.")
        dialogues = read_dialogues(options["input"])
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        target_files = [output_dir / f"{name.lower()}_features.jsonl" for name in POLICIES]
        target_files.append(output_dir / "summary.json")
        existing = [str(path) for path in target_files if path.exists()]
        if existing:
            raise CommandError("Refusing to overwrite: " + ", ".join(existing))

        # Prefer the annotation-time catalog to keep every policy replay comparable.
        catalog = (
            read_menu_snapshot(options["menu_snapshot"])
            if options["menu_snapshot"]
            else load_menu_catalog()
        )
        catalog_ids = {item["id"] for item in catalog}
        for dialogue in dialogues:
            unknown_ids = {
                str(item.get("menu_item_id"))
                for item in dialogue["gold_order"]["items"]
                if str(item.get("menu_item_id")) not in catalog_ids
            }
            if unknown_ids:
                raise CommandError(
                    f"Dialogue {dialogue['dialogue_id']} references menu IDs not in the live catalog: "
                    + ", ".join(sorted(unknown_ids))
                )

        summaries = {}
        for policy in POLICIES:
            feature_rows = []
            dialogue_results = []
            turns_seen = []
            total_questions = 0
            total_latency_ms = 0.0
            total_tokens = 0
            missed = 0
            wrong_turns = 0
            unnecessary = 0
            correct_turns = 0

            for dialogue in dialogues:
                session_id = uuid.uuid4()
                state = initial_session(user_id=0)
                utterances = [dialogue["initial_utterance"]]
                replies = list(dialogue.get("clarification_replies", []))
                reply_index = 0
                final_result = None
                dialogue_turn_count = 0

                while utterances and dialogue_turn_count < options["max_turns"]:
                    utterance = utterances.pop(0)
                    started = time.perf_counter()
                    result, state = parse_customer_turn(
                        session_id,
                        0,
                        utterance,
                        state,
                        configuration=policy,
                        catalog_override=catalog,
                    )
                    latency_ms = (time.perf_counter() - started) * 1000
                    dialogue_turn_count += 1
                    total_latency_ms += latency_ms
                    total_tokens += result["token_usage"]["prompt_tokens"]
                    total_tokens += result["token_usage"]["completion_tokens"]
                    final_result = result

                    wrong = not matches_gold(result, dialogue["gold_order"])
                    asks = result["action"] in ("ASK", "REPAIR")
                    raw_validation = result["raw_validation"]
                    wrong_turns += int(wrong)
                    correct_turns += int(not wrong)
                    missed += int(wrong and not asks)
                    unnecessary += int((not wrong) and asks)
                    total_questions += int(asks)
                    signals = result["signals"]
                    feature_rows.append(
                        {
                            "dialogue_id": str(dialogue["dialogue_id"]),
                            "category": dialogue["category"],
                            "source_group": dialogue["source_group"],
                            "configuration": policy,
                            "turn_index": dialogue_turn_count,
                            "features": signals,
                            "wrong": bool(wrong),
                            "model_requested_clarification": result[
                                "model_requested_clarification"
                            ],
                            "validation_violation": bool(raw_validation["violations"]),
                            "missing_required_count": (
                                len(raw_validation["missing_details"])
                                + sum(
                                    violation["code"] in ("empty_order", "missing_location")
                                    for violation in raw_validation["violations"]
                                )
                            ),
                            "near_match_count": signals["s3"],
                        }
                    )
                    if asks and reply_index < len(replies):
                        utterances.append(replies[reply_index])
                        reply_index += 1
                    else:
                        break

                if final_result is None:
                    continue
                exact = matches_gold(final_result, dialogue["gold_order"])
                final_valid = bool(final_result["valid_for_submission"])
                turns_seen.append(dialogue_turn_count)
                dialogue_results.append(
                    {
                        "exact": exact,
                        "valid": final_valid,
                        "invalid": not final_valid,
                    }
                )

            count = len(dialogue_results)
            summary = {
                "dialogues": count,
                "turns": sum(turns_seen),
                "exact_order_accuracy": sum(row["exact"] for row in dialogue_results) / count,
                "successful_valid_exact_rate": sum(
                    row["exact"] and row["valid"] for row in dialogue_results
                ) / count,
                "invalid_final_draft_rate": sum(
                    row["invalid"] for row in dialogue_results
                ) / count,
                "missed_clarification_rate": missed / wrong_turns if wrong_turns else None,
                "unnecessary_clarification_rate": (
                    unnecessary / correct_turns if correct_turns else None
                ),
                "questions_per_dialogue": total_questions / count,
                "mean_turns_per_dialogue": sum(turns_seen) / count,
                "mean_turn_latency_ms": total_latency_ms / sum(turns_seen),
                "mean_tokens_per_dialogue": total_tokens / count,
                "wrong_turns": wrong_turns,
                "correct_turns": correct_turns,
            }
            summaries[policy] = summary
            _write_jsonl(output_dir / f"{policy.lower()}_features.jsonl", feature_rows)

        (output_dir / "summary.json").write_text(
            json.dumps(summaries, indent=2), encoding="utf-8"
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(summaries, indent=2)))
