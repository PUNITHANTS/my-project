"""Tests for the fixes chosen from the dataset v2 failures (data/evaluations/v2/REPORT.md)."""

import uuid
from unittest import mock

from django.test import SimpleTestCase, override_settings

from .canonicalize import canonicalize_draft
from .services import parse_customer_turn
from .sessions import initial_session
from .test_evaluation_fixes import USAGE, _draft, _item

SIZE = {"id": 1, "name": "Size", "required": True, "min_selections": 1,
        "max_selections": 1, "options": ["Small", "Large", "Extra large"]}
TOPPINGS = {"id": 2, "name": "Toppings", "required": False, "min_selections": 0,
            "max_selections": 5, "options": ["Olives", "Onions", "Ham", "Peppers"]}
EXTRAS = {"id": 3, "name": "Extras", "required": False, "min_selections": 0,
          "max_selections": 3, "options": ["Mayo", "No mayo"]}
WRAP = {"id": 4, "name": "Wrap", "required": True, "min_selections": 1,
        "max_selections": 1, "options": ["White wrap", "Wheat wrap"]}
CATALOG = [
    _item("601", "Pizza", 6, [SIZE, TOPPINGS]),
    _item("101", "Classic Chicken Burger", 1, [EXTRAS]),
    _item("104", "Veggie Burger", 1, [EXTRAS]),
    _item("110", "Coke", 1),
    _item("206", "Chocolate Chip Cookie", 1),
    _item("301", "Veggie Wrap", 1, [WRAP]),
    _item("302", "Chicken Wrap", 1, [WRAP]),
]
LOCATIONS = ["Calcia Hall", "College Hall", "Library"]


def _lines(parsed):
    return [(line.menu_item_id, line.quantity, line.customizations) for line in parsed.items]


class OptionCleanupTests(SimpleTestCase):
    def _clean(self, values, text="A pizza."):
        parsed, notes = canonicalize_draft(
            _draft([("601", "a pizza", 1, values)]), text, CATALOG, locations=LOCATIONS
        )
        return _lines(parsed)[0][2], notes

    def test_any_prefix_before_a_colon_is_dropped(self):
        values, _ = self._clean(["Size (required): Large", "Toppings: Ham"])
        self.assertEqual(values, ["Large", "Ham"])

    def test_plural_and_describing_word_match_a_unique_option(self):
        values, _ = self._clean(["Large", "Onion", "Toppings: Black olives", "green peppers"])
        self.assertEqual(values, ["Large", "Onions", "Olives", "Peppers"])

    def test_negated_add_on_is_dropped(self):
        values, notes = self._clean(["Large", "No Ham", "Hold olives"])
        self.assertEqual(values, ["Large"])
        self.assertEqual([n["action"] for n in notes].count("dropped_negated_option"), 2)

    def test_negation_the_menu_does_not_model_is_left_for_the_validator(self):
        values, _ = self._clean(["Large", "No sausage"])
        self.assertEqual(values, ["Large", "No sausage"])

    def test_negation_that_is_a_menu_option_is_kept(self):
        parsed, _ = canonicalize_draft(
            _draft([("101", "burger", 1, ["No mayo"])]), "A burger, no mayo.", CATALOG
        )
        self.assertEqual(_lines(parsed), [("101", 1, ["No mayo"])])

    def test_unmatched_value_is_left_for_the_validator(self):
        values, _ = self._clean(["Large", "Pineapple"])
        self.assertEqual(values, ["Large", "Pineapple"])


class LocationFallbackTests(SimpleTestCase):
    def test_named_location_fills_an_empty_one(self):
        parsed, notes = canonicalize_draft(
            _draft([("110", "a coke", 1, [])], location=None),
            "Can Calcia Hall get a coke?", CATALOG, locations=LOCATIONS,
        )
        self.assertEqual(parsed.delivery_location, "Calcia Hall")
        self.assertEqual(notes[-1]["action"], "filled_named_location")

    def test_two_locations_fill_nothing(self):
        parsed, _ = canonicalize_draft(
            _draft([("110", "a coke", 1, [])], location=None),
            "I'm at College Hall, no wait, Calcia Hall.", CATALOG, locations=LOCATIONS,
        )
        self.assertIsNone(parsed.delivery_location)

    def test_model_location_is_not_overridden(self):
        parsed, _ = canonicalize_draft(
            _draft([("110", "a coke", 1, [])], location="Library"),
            "A coke from College Hall's cafe to the library.", CATALOG, locations=LOCATIONS,
        )
        self.assertEqual(parsed.delivery_location, "Library")


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65,
                   AI_DELIVERY_LOCATIONS=LOCATIONS)
class PreservationTests(SimpleTestCase):
    def _turns(self, steps):
        state = initial_session(0)
        session = uuid.uuid4()
        result = None
        for draft, text in steps:
            with mock.patch(
                "apps.conversational_ordering.services.interpret_turn",
                return_value=(draft, dict(USAGE)),
            ):
                result, state = parse_customer_turn(
                    session, 0, text, state, configuration="C3", catalog_override=CATALOG
                )
        return [(line["menuItemId"], line["quantity"]) for line in result["items"]]

    FIRST = (_draft([("110", "a coke", 1, []), ("206", "two cookies", 2, [])]),
             "A coke and two chocolate chip cookies to the Library.")

    def test_named_line_dropped_by_the_model_stays_removed(self):
        items = self._turns([self.FIRST, (_draft([("110", "a coke", 1, [])]), "Never mind the chocolate chip cookie.")])
        self.assertEqual(items, [("110", 1)])

    def test_named_line_kept_by_the_model_is_removed_on_a_removal_verb(self):
        steps = [self.FIRST, (_draft([("110", "a coke", 1, []), ("206", "cookie", 2, [])]),
                              "Could I drop the chocolate chip cookie, please?")]
        self.assertEqual(self._turns(steps), [("110", 1)])
        steps[1] = (steps[1][0], "Actually, can we take the chocolate chip cookies out?")
        self.assertEqual(self._turns(steps), [("110", 1)])

    def test_unnamed_line_dropped_by_the_model_is_restored(self):
        items = self._turns([self.FIRST, (_draft([("110", "a coke", 2, [])]), "Make it two cokes.")])
        self.assertEqual(sorted(items), [("110", 2), ("206", 2)])

    def test_removal_verb_on_an_option_keeps_the_line(self):
        first = (_draft([("101", "a burger", 1, ["Mayo"])]), "A classic chicken burger with mayo to the Library.")
        second = (_draft([("101", "burger", 1, [])]), "Skip the mayo on the classic chicken burger.")
        self.assertEqual(self._turns([first, second]), [("101", 1)])

    def test_vague_line_is_replaced_and_keeps_its_quantity(self):
        first = (_draft([("302", "two wraps", 2, ["White wrap"]), ("110", "a coke", 1, [])]),
                 "Two wraps on white and a coke to the Library.")
        second = (_draft([("301", "the veggie one", 1, ["White wrap"]), ("110", "a coke", 1, [])]),
                  "The veggie one.")
        self.assertEqual(sorted(self._turns([first, second])), [("110", 1), ("301", 2)])

    def test_stated_quantity_wins_over_the_vague_line(self):
        first = (_draft([("101", "two burgers", 2, [])]), "Two burgers to the Library.")
        second = (_draft([("104", "one veggie burger", 1, [])]), "Just one veggie burger.")
        self.assertEqual(self._turns([first, second]), [("104", 1)])


SAME_NAME_CATALOG = [
    {**_item("1", "Chicken burger", 1), "vendor": "Hawk Grill"},
    {**_item("2", "Chicken Burger", 2), "vendor": "Street Shack"},
    {**_item("3", "Fries", 2), "vendor": "Street Shack"},
]


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65,
                   AI_DELIVERY_LOCATIONS=["Blanton Hall", "Student Center"])
class SameNameAtTwoRestaurantsTests(SimpleTestCase):
    """Kiosk run of 2026-11-19: "i need a chicken burger" with two vendors selling one."""

    def test_item_is_asked_first_with_restaurant_names(self):
        from .services import apply_selected_option

        state = initial_session(0)
        session = uuid.uuid4()
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=(_draft([(None, "i need a chicken burger", 1, [])], location=None), dict(USAGE)),
        ):
            result, state = parse_customer_turn(
                session, 0, "i need a chicken burger", state, configuration="C3",
                catalog_override=SAME_NAME_CATALOG,
            )
        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(
            result["message"],
            "Chicken burger is sold by Hawk Grill and Street Shack. Which restaurant should it come from?",
        )
        self.assertEqual(
            [option["label"] for option in result["options"]],
            ["Chicken burger (Hawk Grill)", "Chicken Burger (Street Shack)"],
        )
        self.assertEqual(result["cart"]["items"][0]["name"], "a chicken burger (not chosen yet)")

        with mock.patch("apps.conversational_ordering.services.interpret_turn") as interpret:
            result, state = apply_selected_option(
                session, 0, {"slot": "item:0", "menuItemId": "2"}, state,
                catalog_override=SAME_NAME_CATALOG,
            )
        interpret.assert_not_called()
        self.assertEqual(result["message"], "Where should I deliver the order?")
        self.assertEqual(result["cart"]["items"][0]["name"], "Chicken Burger")
        self.assertEqual(result["cart"]["vendorName"], "Street Shack")


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65,
                   AI_DELIVERY_LOCATIONS=["Blanton Hall", "Student Center"])
class SameNameWhateverTheModelSaysTests(SimpleTestCase):
    """The model sometimes picks one of two same-name items and sometimes none; the customer must see the same thing."""

    def _first(self, line_id, text="i need a chicken burger", location=None):
        state = initial_session(0)
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=(_draft([(line_id, "i need a chicken burger", 1, [])], location=location), dict(USAGE)),
        ):
            result, _ = parse_customer_turn(
                uuid.uuid4(), 0, text, state, configuration="C3", catalog_override=SAME_NAME_CATALOG,
            )
        return result

    def test_model_pick_and_model_blank_give_the_same_turn(self):
        picked, blank = self._first("2"), self._first(None)
        for key in ("action", "message", "options"):
            self.assertEqual(picked[key], blank[key])
        self.assertEqual(picked["cart"]["items"], blank["cart"]["items"])
        self.assertEqual(picked["cart"]["items"][0]["name"], "a chicken burger (not chosen yet)")
        self.assertIn("Which restaurant", picked["message"])

    def test_model_pick_is_not_confirmed_even_with_a_location(self):
        result = self._first("1", location="Blanton Hall")
        self.assertNotEqual(result["action"], "CONFIRM")
        self.assertIn("Which restaurant", result["message"])

    def test_cart_restaurant_decides(self):
        state = initial_session(0)
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=(_draft([("3", "fries", 1, []), ("1", "a chicken burger", 1, [])], location="Blanton Hall"),
                          dict(USAGE)),
        ):
            result, _ = parse_customer_turn(
                uuid.uuid4(), 0, "Fries and a chicken burger to Blanton Hall.", state,
                configuration="C3", catalog_override=SAME_NAME_CATALOG,
            )
        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(sorted(line["menuItemId"] for line in result["cart"]["items"]), ["2", "3"])
        self.assertEqual(result["cart"]["vendorName"], "Street Shack")

    def test_unique_full_name_is_still_settled(self):
        state = initial_session(0)
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=(_draft([("3", "fries", 1, [])], location="Blanton Hall"), dict(USAGE)),
        ):
            result, _ = parse_customer_turn(
                uuid.uuid4(), 0, "Fries to Blanton Hall.", state,
                configuration="C3", catalog_override=SAME_NAME_CATALOG,
            )
        self.assertEqual(result["action"], "CONFIRM")


@override_settings(AI_SAMPLE_AGREEMENT_K=0, AI_MAX_QUESTIONS=5, AI_NEAR_MATCH_THRESHOLD=0.65,
                   AI_DELIVERY_LOCATIONS=["Blanton Hall"])
class UnavailableNamedItemTests(SimpleTestCase):
    """gemma3:12b picked an unavailable item the customer named in full; this used to crash."""

    def test_unavailable_named_item_is_repaired_not_crashed(self):
        catalog = [dict(_item("9", "Seasonal Soup", 1), available=False), _item("3", "Fries", 1)]
        state = initial_session(0)
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=(_draft([("9", "seasonal soup", 1, [])], location="Blanton Hall"), dict(USAGE)),
        ):
            result, _ = parse_customer_turn(
                uuid.uuid4(), 0, "A seasonal soup to Blanton Hall.", state,
                configuration="C3", catalog_override=catalog,
            )
        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(result["validation"]["violations"][0]["code"], "unavailable_item")
