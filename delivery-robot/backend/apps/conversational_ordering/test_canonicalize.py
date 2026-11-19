"""Tests for the draft clean-up rules, each taken from a failing test-split dialogue."""

import uuid
from unittest import mock

from django.test import SimpleTestCase, override_settings

from .canonicalize import canonicalize_draft
from .services import parse_customer_turn
from .sessions import initial_session
from .test_evaluation_fixes import USAGE, _draft, _item

SIZE = {"id": 1, "name": "Size", "required": True, "min_selections": 1,
        "max_selections": 1, "options": ["Small", "Regular", "Large"]}
PIZZA_SIZE = {"id": 2, "name": "Size", "required": True, "min_selections": 1,
              "max_selections": 1, "options": ["Personal", "Large"]}
SAUCE = {"id": 3, "name": "Sauce", "required": True, "min_selections": 1,
         "max_selections": 1, "options": ["Teriyaki", "Garlic", "No sauce"]}
EXTRAS = {"id": 4, "name": "Extras", "required": False, "min_selections": 0,
          "max_selections": 3, "options": ["Mayo", "No mayo", "Ketchup"]}
CATALOG = [
    _item("101", "Classic Chicken Burger", 1, [EXTRAS]),
    _item("102", "Spicy Chicken Burger", 1, [EXTRAS]),
    _item("204", "Coffee", 2, [SIZE]),
    _item("403", "Veggie Pizza", 2, [PIZZA_SIZE]),
    _item("504", "Tofu Rice Bowl", 2, [SAUCE]),
]


def _lines(parsed):
    return [(line.menu_item_id, line.quantity, line.customizations) for line in parsed.items]


class CanonicalizeTests(SimpleTestCase):
    def test_group_name_prefix_is_removed(self):
        for value, expected in (("Size: Regular", "Regular"), ("size regular", "Regular")):
            parsed, notes = canonicalize_draft(
                _draft([("204", "a regular coffee", 1, [value])]), "A regular coffee.", CATALOG
            )
            self.assertEqual(_lines(parsed), [("204", 1, [expected])])
            self.assertEqual(notes[0]["action"], "canonical_option")
        parsed, _ = canonicalize_draft(
            _draft([("504", "tofu bowl", 2, ["Sauce Teriyaki"])]), "Tofu bowl.", CATALOG
        )
        self.assertEqual(_lines(parsed), [("504", 2, ["Teriyaki"])])

    def test_unknown_option_is_left_for_the_validator(self):
        parsed, _ = canonicalize_draft(
            _draft([("204", "coffee", 1, ["Size: Huge"])]), "A huge coffee.", CATALOG
        )
        self.assertEqual(_lines(parsed), [("204", 1, ["Size: Huge"])])

    def test_required_option_said_by_the_customer_is_filled(self):
        parsed, _ = canonicalize_draft(
            _draft([("204", "two coffees", 2, [])]), "Two small coffees.", CATALOG
        )
        self.assertEqual(_lines(parsed), [("204", 2, ["Small"])])

    def test_two_options_named_fills_nothing(self):
        parsed, _ = canonicalize_draft(
            _draft([("204", "coffee", 1, [])]), "A small or large coffee?", CATALOG
        )
        self.assertEqual(_lines(parsed), [("204", 1, [])])

    def test_option_for_another_item_is_not_borrowed(self):
        # "large" belongs to the coffee; the pizza must still be asked about.
        parsed, _ = canonicalize_draft(
            _draft([("204", "a large coffee", 1, ["Large"]), ("403", "a veggie pizza", 1, [])]),
            "A large coffee and a veggie pizza.",
            CATALOG,
        )
        self.assertEqual(_lines(parsed), [("204", 1, ["Large"]), ("403", 1, [])])

    def test_longer_option_wins_over_one_it_contains(self):
        parsed, _ = canonicalize_draft(
            _draft([("504", "tofu bowl", 1, [])]), "A tofu bowl, no sauce.", CATALOG
        )
        self.assertEqual(_lines(parsed), [("504", 1, ["No sauce"])])

    def test_earlier_choice_is_kept_when_the_quantity_changes(self):
        previous = _draft([("403", "a personal veggie pizza", 1, ["Personal"])]).model_dump(mode="json")
        parsed, _ = canonicalize_draft(
            _draft([("403", "a personal veggie pizza", 2, [])]), "Actually, make that two.", CATALOG, previous
        )
        self.assertEqual(_lines(parsed), [("403", 2, ["Personal"])])

    def test_one_of_them_takes_one_from_the_plain_line(self):
        parsed, _ = canonicalize_draft(
            _draft([("101", "two classic burgers", 2, []), ("101", "one with ketchup", 1, ["Ketchup"])]),
            "Two classic chicken burgers, one of them with ketchup, deliver to Calcia Hall.",
            CATALOG,
        )
        self.assertEqual(_lines(parsed), [("101", 1, []), ("101", 1, ["Ketchup"])])

    def test_one_of_them_leaves_a_correct_split_alone(self):
        parsed, notes = canonicalize_draft(
            _draft([("101", "burger", 1, []), ("101", "one with ketchup", 1, ["Ketchup"])]),
            "Two classic chicken burgers, one of them with ketchup.",
            CATALOG,
        )
        self.assertEqual(_lines(parsed), [("101", 1, []), ("101", 1, ["Ketchup"])])
        self.assertEqual(notes, [])

    def test_empty_customization_is_dropped(self):
        parsed, _ = canonicalize_draft(
            _draft([("101", "burger", 1, ["No mayo", ""])]), "A burger, no mayo.", CATALOG
        )
        self.assertEqual(_lines(parsed), [("101", 1, ["No mayo"])])


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65)
class CorrectionReplacementTests(SimpleTestCase):
    def test_change_that_to_replaces_the_only_line(self):
        state = initial_session(0)
        session = uuid.uuid4()
        results = []
        for draft, text in (
            (_draft([("101", "a classic chicken burger", 1, [])]), "I want a classic chicken burger sent to Library."),
            (_draft([("102", "three spicy chicken burgers", 3, [])]), "Change that to three spicy chicken burgers."),
        ):
            with mock.patch(
                "apps.conversational_ordering.services.interpret_turn",
                return_value=(draft, dict(USAGE)),
            ):
                result, state = parse_customer_turn(
                    session, 0, text, state, configuration="C3", catalog_override=CATALOG
                )
            results.append(result)
        self.assertEqual(
            [(line["menuItemId"], line["quantity"]) for line in results[1]["items"]], [("102", 3)]
        )
        self.assertEqual(results[1]["action"], "CONFIRM")
