"""Regression tests for the C1-C5 evaluation failures found in the full run.

Each test reproduces a pattern seen in the replay traces; the model call is
mocked, so no database, Redis or API key is needed.
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from .groq_client import compact_menu
from .menu_validation import _candidate_items, names_item
from .schemas import ParsedOrder
from .services import parse_customer_turn
from .sessions import initial_session


def _item(item_id, name, vendor_id, groups=()):
    return {
        "id": item_id,
        "name": name,
        "description": "",
        "price": "5.00",
        "vendor_id": vendor_id,
        "vendor": f"Vendor {vendor_id}",
        "vendor_location": "Hall",
        "available": True,
        "max_quantity": 5,
        "option_groups": list(groups),
    }


SIZE = {"id": 1, "name": "Size", "required": True, "min_selections": 1,
        "max_selections": 1, "options": ["Personal", "Large"]}
CATALOG = [
    _item("101", "Classic Chicken Burger", 1),
    _item("102", "Spicy Chicken Burger", 1),
    _item("103", "Grilled Chicken Burger", 1),
    _item("104", "Veggie Burger", 1),
    _item("105", "Chicken Wrap", 1),
    _item("108", "Chicken Tenders", 1),
    _item("202", "Cola", 2),
    _item("208", "Hot Chocolate", 2),
    _item("401", "Cheese Pizza", 4, [SIZE]),
    _item("403", "Veggie Pizza", 4, [SIZE]),
]


def _draft(lines, location="Library", clarification=None):
    return ParsedOrder.model_validate(
        {
            "items": [
                {
                    "menu_item_id": item_id,
                    "mention": mention,
                    "quantity": quantity,
                    "customizations": customizations,
                    "confidence": {"item": 0.9, "quantity": 0.95, "customization": 0.9},
                }
                for item_id, mention, quantity, customizations in lines
            ],
            "delivery_location": location,
            "confidence": 0.9,
            "delivery_location_confidence": 0.95,
            "clarification_needed": clarification,
        }
    )


USAGE = {"prompt_tokens": 1, "completion_tokens": 1}


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65)
class ConversationFixTests(SimpleTestCase):
    def _turns(self, drafts, utterances, policy="C3"):
        state = initial_session(0)
        session = uuid.uuid4()
        results = []
        for draft, utterance in zip(drafts, utterances):
            with mock.patch(
                "apps.conversational_ordering.services.interpret_turn",
                return_value=(draft, dict(USAGE)),
            ):
                result, state = parse_customer_turn(
                    session, 0, utterance, state, configuration=policy, catalog_override=CATALOG
                )
            results.append(result)
        return results

    def test_a_full_item_name_is_not_ambiguous(self):
        # Was: "two grilled chicken burgers" matched all three chicken burgers.
        candidates = _candidate_items("two grilled chicken burgers", CATALOG, 0.65)
        self.assertEqual([c["menu_item_id"] for c in candidates], ["103"])
        candidates = _candidate_items("two chicken wraps", CATALOG, 0.65)
        self.assertEqual([c["menu_item_id"] for c in candidates], ["105"])
        self.assertTrue(names_item("Two personal cheese pizzas", "Cheese Pizza"))

    def test_a_vague_word_is_still_ambiguous(self):
        candidates = _candidate_items("a burger", CATALOG, 0.65)
        self.assertEqual(
            {c["menu_item_id"] for c in candidates}, {"101", "102", "103", "104"}
        )
        # Was: "two" stopped "two pizzas" from matching any pizza.
        candidates = _candidate_items("two pizzas", CATALOG, 0.65)
        self.assertEqual({c["menu_item_id"] for c in candidates}, {"401", "403"})

    def test_clear_request_confirms_without_a_question(self):
        (result,) = self._turns(
            [_draft([("103", "two grilled chicken burgers", 2, [])])],
            ["I'd like two grilled chicken burgers, delivered to Library."],
        )
        self.assertEqual(result["action"], "CONFIRM")

    def test_answer_replaces_the_guessed_line_instead_of_adding_to_it(self):
        # Was: the guessed Classic burger was restored next to the answer.
        first, second = self._turns(
            [
                _draft([("101", "a burger", 1, [])]),
                _draft([("103", "grilled chicken burger", 1, [])]),
            ],
            ["I'll have a burger, deliver to Library.", "A grilled chicken burger."],
        )
        self.assertEqual(first["action"], "ASK")
        self.assertEqual([line["menuItemId"] for line in second["items"]], ["103"])
        self.assertEqual(second["action"], "CONFIRM")

    def test_naming_the_item_settles_the_question_even_if_the_mention_is_stale(self):
        # Was: the model kept mention "a burger", so the same question repeated.
        _, second = self._turns(
            [
                _draft([("101", "a burger", 1, [])]),
                _draft([("101", "a burger", 1, [])]),
            ],
            ["I'll have a burger, deliver to Library.", "A classic chicken burger."],
        )
        self.assertEqual(second["action"], "CONFIRM")

    def test_unknown_item_answer_drops_the_placeholder_line(self):
        # Was: [None, "two pizzas"] stayed in the cart after the customer answered.
        first, second = self._turns(
            [
                _draft([(None, "two pizzas", 2, [])]),
                _draft([("403", "two personal veggie pizzas", 2, ["Personal"])]),
            ],
            ["I'll have two pizzas, deliver to Library.", "Two personal veggie pizzas."],
        )
        self.assertEqual(first["action"], "REPAIR")
        self.assertEqual({o["menuItemId"] for o in first["options"]}, {"401", "403"})
        self.assertEqual(
            [(line["menuItemId"], line["quantity"]) for line in second["items"]], [("403", 2)]
        )
        self.assertEqual(second["action"], "CONFIRM")

    def test_a_guess_unrelated_to_the_wording_is_asked_about(self):
        # Was: "two drinks" became Cola and was confirmed without a question.
        (result,) = self._turns(
            [_draft([("202", "two drinks", 2, [])])],
            ["I'll have two drinks, deliver to Library."],
        )
        self.assertEqual(result["action"], "ASK")
        self.assertIn("208", {option["menuItemId"] for option in result["options"]})

    def test_an_unrelated_line_is_still_preserved(self):
        _, second = self._turns(
            [
                _draft([("108", "chicken tenders", 1, []), ("101", "a burger", 1, [])]),
                _draft([("103", "grilled chicken burger", 1, [])]),
            ],
            ["Chicken tenders and a burger to Library.", "A grilled chicken burger."],
        )
        self.assertEqual(sorted(line["menuItemId"] for line in second["items"]), ["103", "108"])


class CompactPromptTests(SimpleTestCase):
    def test_compact_menu_keeps_ids_names_and_options(self):
        lines = compact_menu(CATALOG)
        self.assertIn("401 | Cheese Pizza | Vendor 4 | Size (required): Personal, Large", lines)
        full = len(json.dumps(CATALOG))
        self.assertLess(len(json.dumps(lines)), full / 2)


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65)
class ExperimentRunnerTests(SimpleTestCase):
    def test_correction_is_delivered_after_confirmation_and_scored(self):
        dialogue = {
            "dialogue_id": "correction-1",
            "category": "correction",
            "source_group": "g1",
            "initial_utterance": "One cola to Library.",
            "clarification_replies": ["Actually, make that two."],
            "gold_order": {
                "vendor_id": 2,
                "delivery_location": "Library",
                "items": [{"menu_item_id": "202", "quantity": 2, "customizations": []}],
            },
        }
        drafts = iter([
            (_draft([("202", "cola", 1, [])]), dict(USAGE)),
            (_draft([("202", "cola", 2, [])]), dict(USAGE)),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "d.jsonl").write_text(json.dumps(dialogue) + "\n", encoding="utf-8")
            (tmp / "menu.json").write_text(json.dumps({"items": CATALOG}), encoding="utf-8")
            with mock.patch(
                "apps.conversational_ordering.services.interpret_turn",
                side_effect=lambda *args, **kwargs: next(drafts),
            ):
                call_command(
                    "run_conversation_experiments",
                    input=str(tmp / "d.jsonl"),
                    output_dir=str(tmp / "out"),
                    menu_snapshot=str(tmp / "menu.json"),
                    policies="C3",
                    trace=True,
                    stdout=mock.MagicMock(),
                )
            summary = json.loads((tmp / "out" / "summary.json").read_text())["C3"]
            rows = [
                json.loads(line)
                for line in (tmp / "out" / "c3_features.jsonl").read_text().splitlines()
            ]
            trace = (tmp / "out" / "c3_trace.jsonl").read_text().splitlines()

        self.assertEqual(summary["exact_order_accuracy"], 1.0)
        self.assertEqual(summary["by_category"]["correction"]["exact_order_accuracy"], 1.0)
        # Turn 1 matched what was asked for, but not yet the corrected gold order.
        self.assertEqual([row["label_valid"] for row in rows], [False, True])
        self.assertEqual(summary["wrong_turns"] + summary["correct_turns"], 1)
        self.assertEqual(len(trace), 2)


class LocalServerRetryTests(SimpleTestCase):
    @override_settings(AI_EXPERIMENT_MODE=True)
    def test_repeat_limit_error_is_retried_with_a_seeded_temperature(self):
        # Ollama answers 500 "token repeat limit reached" when greedy decoding loops.
        import urllib.request

        from . import groq_client

        sent = []

        class Response:
            def __init__(self, status, payload):
                self.status, self._payload, self.reason, self.headers = status, payload, "", {}

            def read(self):
                return self._payload

            def getheader(self, name):
                return None

        replies = iter([
            Response(500, b'{"error":{"message":"prediction aborted, token repeat limit reached"}}'),
            Response(200, b'{"ok": true}'),
        ])

        class Connection:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, method, path, body=None, headers=None):
                sent.append(json.loads(body))

            def getresponse(self):
                return next(replies)

            def close(self):
                pass

        request = urllib.request.Request(
            "http://localhost:11434/v1/chat/completions",
            data=json.dumps({"model": "m", "temperature": 0}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with mock.patch.object(groq_client.http.client, "HTTPConnection", Connection), \
                mock.patch.object(groq_client.time, "sleep"):
            result = groq_client._post_with_rate_limit_retry(request)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(sent[0]["temperature"], 0)
        self.assertEqual((sent[1]["temperature"], sent[1]["seed"]), (0.3, 1))
