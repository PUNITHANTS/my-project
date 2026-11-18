"""Tests for the kiosk turn contract: options, tapped options and cart edits.

They run without a database, Redis or a Groq key: the menu is a fixture and the
model call is mocked.
"""

import uuid
from types import SimpleNamespace
from unittest import mock

from django.core import signing
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .groq_client import AIProviderError
from .schemas import ParsedOrder
from .services import (
    CONFIRMATION_SALT,
    InvalidTurnInput,
    apply_cart_edit,
    apply_selected_option,
    parse_customer_turn,
    submission_cart_signature,
)
from .sessions import initial_session
from .views import ParseOrderView


def _item(item_id, name, vendor_id, vendor, option_groups=(), max_quantity=10, available=True):
    return {
        "id": item_id,
        "name": name,
        "description": "",
        "price": "5.00",
        "vendor_id": vendor_id,
        "vendor": vendor,
        "vendor_location": "Hall",
        "available": available,
        "max_quantity": max_quantity,
        "option_groups": list(option_groups),
    }


SIZE = {
    "id": 1,
    "name": "Size",
    "required": True,
    "min_selections": 1,
    "max_selections": 1,
    "options": ["Regular", "Large"],
}
EXTRAS = {
    "id": 2,
    "name": "Extras",
    "required": False,
    "min_selections": 0,
    "max_selections": 2,
    "options": ["Cheese", "Bacon"],
}
CATALOG = [
    _item("1", "Crispy Chicken Burger", 1, "Grill", [SIZE, EXTRAS]),
    _item("2", "Grilled Chicken Burger", 1, "Grill"),
    _item("3", "Soda", 1, "Grill", max_quantity=4),
    _item("4", "Veggie Wrap", 2, "Cafe"),
]
USAGE = {"prompt_tokens": 10, "completion_tokens": 5}
SESSION = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER = 7


def _parsed(lines, location="Library"):
    return ParsedOrder.model_validate(
        {
            "items": [
                {
                    "menu_item_id": item_id,
                    "mention": mention,
                    "quantity": quantity,
                    "customizations": customizations,
                    "confidence": {"item": 0.9, "quantity": 0.9, "customization": 0.9},
                }
                for item_id, mention, quantity, customizations in lines
            ],
            "delivery_location": location,
            "confidence": 0.9,
            "delivery_location_confidence": 0.9,
            "clarification_needed": None,
        }
    )


@override_settings(
    AI_DEFAULT_POLICY="C3",
    AI_SAMPLE_AGREEMENT_K=0,
    AI_MAX_QUESTIONS=5,
    AI_NEAR_MATCH_THRESHOLD=0.9,
    AI_DELIVERY_LOCATIONS=["Student Center", "Library"],
)
class TurnServiceTests(SimpleTestCase):
    def _first_turn(self, parsed):
        state = initial_session(USER)
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=(parsed, dict(USAGE)),
        ):
            return parse_customer_turn(
                SESSION, USER, "order text", state, catalog_override=CATALOG
            )

    def _tap(self, state, option):
        selected = {key: option[key] for key in ("slot", "menuItemId", "value") if key in option}
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn"
        ) as interpret:
            result = apply_selected_option(
                SESSION, USER, selected, state, catalog_override=CATALOG
            )
        interpret.assert_not_called()
        return result

    def _edit(self, state, line, quantity):
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn"
        ) as interpret:
            result = apply_cart_edit(
                SESSION, USER, {"line": line, "quantity": quantity}, state,
                catalog_override=CATALOG,
            )
        interpret.assert_not_called()
        return result

    def test_unknown_item_offers_menu_items_and_a_tap_resolves_it(self):
        result, state = self._first_turn(_parsed([(None, "chicken burger", 2, [])]))

        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(
            [(option["slot"], option["label"]) for option in result["options"]],
            [("item:0", "Crispy Chicken Burger"), ("item:0", "Grilled Chicken Burger")],
        )
        self.assertEqual(result["message"], result["clarificationNeeded"])

        grilled = result["options"][1]
        result, state = self._tap(state, grilled)

        self.assertFalse(result["llm_called"])
        self.assertEqual(result["token_usage"], {"prompt_tokens": 0, "completion_tokens": 0})
        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(result["options"], [])
        self.assertEqual(
            result["cart"]["items"],
            [
                {
                    "line": 0,
                    "menuItemId": "2",
                    "name": "Grilled Chicken Burger",
                    "quantity": 2,
                    "customization": "",
                    "customizations": [],
                    "unitPrice": "5.00",
                }
            ],
        )
        self.assertEqual(result["cart"]["vendorName"], "Grill")
        self.assertTrue(result["confirmation_token"])

    def test_ambiguous_mention_is_not_asked_again_after_a_tap(self):
        result, state = self._first_turn(_parsed([("2", "chicken burger", 1, [])]))
        self.assertEqual(result["action"], "ASK")
        self.assertEqual({option["slot"] for option in result["options"]}, {"item:0"})

        result, state = self._tap(state, result["options"][1])

        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(state["resolved_item_ids"], ["2"])

    def test_required_option_is_answered_by_a_tap(self):
        result, state = self._first_turn(_parsed([("1", "Crispy Chicken Burger", 1, [])]))
        self.assertEqual(result["action"], "ASK")
        self.assertEqual(
            result["options"],
            [
                {"slot": "option:0", "label": "Regular", "value": "Regular"},
                {"slot": "option:0", "label": "Large", "value": "Large"},
            ],
        )

        result, state = self._tap(state, result["options"][1])

        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(result["cart"]["items"][0]["customization"], "Large")

    def test_invalid_customization_can_be_left_out_then_required_option_asked(self):
        result, state = self._first_turn(
            _parsed([("1", "Crispy Chicken Burger", 1, ["no mayo", "Cheese"])])
        )
        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(result["options"][-1]["label"], "Leave it out")

        result, state = self._tap(state, result["options"][-1])

        self.assertEqual(result["cart"]["items"][0]["customizations"], ["Cheese"])
        self.assertEqual(result["action"], "ASK")
        result, state = self._tap(state, result["options"][0])
        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(result["cart"]["items"][0]["customizations"], ["Cheese", "Regular"])

    def test_missing_location_offers_configured_locations(self):
        result, state = self._first_turn(_parsed([("3", "Soda", 1, [])], location=None))
        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(
            result["options"],
            [
                {"slot": "location", "label": "Student Center", "value": "Student Center"},
                {"slot": "location", "label": "Library", "value": "Library"},
            ],
        )

        result, state = self._tap(state, result["options"][1])

        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(result["cart"]["deliveryLocation"], "Library")

    def test_mixed_vendors_offers_vendor_choice(self):
        result, state = self._first_turn(
            _parsed([("3", "Soda", 1, []), ("4", "Veggie Wrap", 1, [])])
        )
        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(
            result["options"],
            [
                {"slot": "vendor", "label": "Grill", "value": "1"},
                {"slot": "vendor", "label": "Cafe", "value": "2"},
            ],
        )

        result, state = self._tap(state, result["options"][1])

        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual([line["name"] for line in result["cart"]["items"]], ["Veggie Wrap"])

    def test_quantity_edit_keeps_the_confirmation_token_in_step_with_the_cart(self):
        result, state = self._first_turn(_parsed([("3", "Soda", 1, [])]))
        self.assertEqual(result["action"], "CONFIRM")

        result, state = self._edit(state, 0, 3)

        self.assertFalse(result["llm_called"])
        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(result["cart"]["items"][0]["quantity"], 3)
        claims = signing.loads(result["confirmation_token"], salt=CONFIRMATION_SALT)
        self.assertEqual(
            claims["cart"],
            submission_cart_signature(
                1, "Library", [{"menu_item_id": 3, "quantity": 3, "customization": ""}]
            ),
        )

    def test_quantity_over_the_limit_is_repaired_with_one_tap(self):
        result, state = self._first_turn(_parsed([("3", "Soda", 1, [])]))

        result, state = self._edit(state, 0, 9)

        self.assertEqual(result["action"], "REPAIR")
        self.assertIsNone(result["confirmation_token"])
        self.assertEqual(
            result["options"],
            [{"slot": "quantity:0", "label": "Make it 4", "value": "4"}],
        )
        result, state = self._tap(state, result["options"][0])
        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(result["cart"]["items"][0]["quantity"], 4)

    def test_removing_a_line_keeps_the_others(self):
        result, state = self._first_turn(
            _parsed([("3", "Soda", 1, []), ("2", "Grilled Chicken Burger", 1, [])])
        )

        result, state = self._edit(state, 0, 0)

        self.assertEqual(result["action"], "CONFIRM")
        self.assertEqual(
            [(line["line"], line["name"]) for line in result["cart"]["items"]],
            [(0, "Grilled Chicken Burger")],
        )

    def test_removing_the_last_line_asks_for_an_order(self):
        result, state = self._first_turn(_parsed([("3", "Soda", 1, [])]))

        result, state = self._edit(state, 0, 0)

        self.assertEqual(result["action"], "REPAIR")
        self.assertEqual(result["cart"]["items"], [])

    def test_an_option_that_was_not_offered_is_rejected(self):
        result, state = self._first_turn(_parsed([(None, "chicken burger", 1, [])]))

        with self.assertRaises(InvalidTurnInput):
            apply_selected_option(
                SESSION, USER, {"slot": "item:0", "menuItemId": "4"}, state,
                catalog_override=CATALOG,
            )

    def test_an_option_from_an_earlier_question_is_rejected(self):
        result, state = self._first_turn(_parsed([(None, "chicken burger", 1, [])]))
        first_question_option = result["options"][1]
        self._tap(state, first_question_option)

        with self.assertRaises(InvalidTurnInput):
            self._tap(state, first_question_option)

    def test_edits_need_an_existing_line(self):
        with self.assertRaises(InvalidTurnInput):
            apply_cart_edit(
                SESSION, USER, {"line": 0, "quantity": 1}, initial_session(USER),
                catalog_override=CATALOG,
            )
        result, state = self._first_turn(_parsed([("3", "Soda", 1, [])]))
        with self.assertRaises(InvalidTurnInput):
            self._edit(state, 5, 1)


@override_settings(
    AI_DEFAULT_POLICY="C3",
    AI_SAMPLE_AGREEMENT_K=0,
    AI_NEAR_MATCH_THRESHOLD=0.9,
    AI_LOG_TURNS=False,
    AI_DELIVERY_LOCATIONS=["Library"],
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class ParseOrderViewTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.session_id = str(uuid.uuid4())
        patcher = mock.patch(
            "apps.conversational_ordering.services.load_menu_catalog", return_value=CATALOG
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, body, interpret_result=None, side_effect=None):
        request = APIRequestFactory().post(
            "/api/ai/parse-order/", {"session_id": self.session_id, **body}, format="json"
        )
        force_authenticate(request, user=SimpleNamespace(pk=USER, is_authenticated=True))
        with mock.patch(
            "apps.conversational_ordering.services.interpret_turn",
            return_value=interpret_result,
            side_effect=side_effect,
        ) as interpret:
            response = ParseOrderView.as_view()(request)
        return response, interpret

    def test_text_then_tapped_option_then_cart_edit(self):
        parsed = _parsed([("3", "Soda", 1, [])], location=None)
        response, interpret = self._post(
            {"transcript": "a soda", "selected_option": None},
            interpret_result=(parsed, dict(USAGE)),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "REPAIR")
        self.assertEqual(interpret.call_count, 1)
        first_turn_id = response.data["turn_id"]
        uuid.UUID(first_turn_id)

        response, interpret = self._post({"selected_option": response.data["options"][0]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "CONFIRM")
        self.assertEqual(response.data["cart"]["deliveryLocation"], "Library")
        self.assertNotEqual(response.data["turn_id"], first_turn_id)
        interpret.assert_not_called()

        response, interpret = self._post({"cart_edit": {"line": 0, "quantity": 2}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["cart"]["items"][0]["quantity"], 2)
        self.assertTrue(response.data["confirmation_token"])
        interpret.assert_not_called()

    def test_exactly_one_input_is_required(self):
        response, _ = self._post({})
        self.assertEqual(response.status_code, 400)
        response, _ = self._post(
            {"transcript": "a soda", "cart_edit": {"line": 0, "quantity": 2}}
        )
        self.assertEqual(response.status_code, 400)

    def test_unoffered_option_is_a_bad_request(self):
        response, _ = self._post({"selected_option": {"slot": "location", "value": "Mars"}})
        self.assertEqual(response.status_code, 400)

    def test_provider_failure_returns_an_error_turn_with_the_current_cart(self):
        parsed = _parsed([("3", "Soda", 2, [])])
        self._post({"transcript": "two sodas"}, interpret_result=(parsed, dict(USAGE)))

        response, _ = self._post(
            {"transcript": "add a wrap"}, side_effect=AIProviderError("Groq is down.")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["action"], "ERROR")
        self.assertEqual(response.data["options"], [])
        self.assertIsNone(response.data["confirmation_token"])
        self.assertEqual(response.data["cart"]["items"][0]["name"], "Soda")
        self.assertEqual(response.data["cart"]["items"][0]["quantity"], 2)
        uuid.UUID(response.data["turn_id"])
