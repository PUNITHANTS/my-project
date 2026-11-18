package com.msu.campuseats.ui.assistant

import com.google.gson.Gson
import com.msu.campuseats.data.remote.AiParseOrderResponse
import com.msu.campuseats.data.remote.ParseOrderRequest
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Drives the view model with canned backend JSON, parsed the way Retrofit parses it. */
@OptIn(ExperimentalCoroutinesApi::class)
class AssistantViewModelTest {
    private val gson = Gson()
    private val gateway = FakeGateway()
    private lateinit var viewModel: AssistantViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
        viewModel = AssistantViewModel(gateway)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun turn(json: String) = gson.fromJson(json, AiParseOrderResponse::class.java)

    private val askWhichBurger = """
        {"action": "ASK", "message": "Which chicken burger would you like?",
         "options": [{"slot": "item:0", "label": "Crispy Chicken Burger", "menuItemId": "1"},
                     {"slot": "item:0", "label": "Grilled Chicken Burger", "menuItemId": "2"}],
         "cart": {"items": [{"line": 0, "menuItemId": "1", "name": "Crispy Chicken Burger",
                             "quantity": 2, "customization": "", "unitPrice": "5.00"}],
                  "vendorId": 1, "vendorName": "Grill", "deliveryLocation": "Library"},
         "confidence": 0.71, "clarificationNeeded": "Which chicken burger would you like?",
         "valid_for_submission": false, "confirmation_token": null, "turn_id": "t-1"}
    """
    private val repairLocation = """
        {"action": "REPAIR", "message": "Where should I deliver the order?",
         "options": [{"slot": "location", "label": "Library", "value": "Library"}],
         "cart": {"items": [{"line": 0, "menuItemId": "3", "name": "Soda", "quantity": 1,
                             "customization": "", "unitPrice": "2.00"}],
                  "vendorId": 1, "vendorName": "Grill", "deliveryLocation": null},
         "valid_for_submission": false, "confirmation_token": null, "turn_id": "t-2"}
    """
    private val confirmSoda = """
        {"action": "CONFIRM", "message": "Please review the cart and confirm.", "options": [],
         "cart": {"items": [{"line": 0, "menuItemId": "3", "name": "Soda", "quantity": 1,
                             "customization": "", "unitPrice": "2.00"}],
                  "vendorId": 1, "vendorName": "Grill", "deliveryLocation": "Library"},
         "valid_for_submission": true, "confirmation_token": "signed-token", "turn_id": "t-3"}
    """
    private val providerError = """
        {"action": "ERROR", "message": "The ordering assistant is unavailable right now.",
         "options": [],
         "cart": {"items": [{"line": 0, "menuItemId": "3", "name": "Soda", "quantity": 1,
                             "customization": "", "unitPrice": "2.00"}],
                  "vendorId": 1, "vendorName": "Grill", "deliveryLocation": null},
         "valid_for_submission": false, "confirmation_token": null, "turn_id": "t-4"}
    """

    @Test
    fun askShowsTheQuestionAndItsOptions() {
        gateway.replies += turn(askWhichBurger)

        viewModel.send("two chicken burgers to the library")

        val state = viewModel.state.value
        assertEquals("two chicken burgers to the library", gateway.requests.single().transcript)
        assertEquals(ChatMessage(ChatRole.ASSISTANT, "Which chicken burger would you like?"), state.messages.last())
        assertEquals(listOf("Crispy Chicken Burger", "Grilled Chicken Burger"), state.options.map { it.label })
        assertTrue(state.hasCartItems)
        assertFalse(state.canConfirm)
        assertFalse(state.offerTouchMenu)
    }

    @Test
    fun tappingAnOptionSendsItBackWithoutText() {
        gateway.replies += turn(askWhichBurger)
        gateway.replies += turn(confirmSoda)
        viewModel.send("two chicken burgers")

        viewModel.selectOption(viewModel.state.value.options[1])

        val request = gateway.requests.last()
        assertNull(request.transcript)
        assertNull(request.cartEdit)
        assertEquals("item:0", request.selectedOption?.slot)
        assertEquals("2", request.selectedOption?.menuItemId)
        assertEquals(gateway.requests.first().sessionId, request.sessionId)
        assertTrue(viewModel.state.value.messages.contains(ChatMessage(ChatRole.USER, "Grilled Chicken Burger")))
        assertTrue(viewModel.state.value.options.isEmpty())
    }

    @Test
    fun repairShowsOptionsAndBlocksConfirm() {
        gateway.replies += turn(repairLocation)

        viewModel.send("a soda")

        val state = viewModel.state.value
        assertEquals("Library", state.options.single().label)
        assertFalse(state.canConfirm)
    }

    @Test
    fun confirmTurnEnablesConfirmAndPlacesTheOrder() {
        gateway.replies += turn(confirmSoda)
        viewModel.send("a soda to the library")
        assertTrue(viewModel.state.value.canConfirm)

        viewModel.confirm("Sam", "555-0100", "")

        assertEquals("signed-token", gateway.placedWith?.confirmationToken)
        assertEquals(41, viewModel.state.value.placedOrderId)
        assertFalse(viewModel.state.value.canConfirm)
    }

    @Test
    fun cartEditSendsLineAndQuantityAndVoidsTheOldConfirmation() {
        gateway.replies += turn(confirmSoda)
        gateway.replies += turn(repairLocation)
        viewModel.send("a soda to the library")

        viewModel.editLine(0, 3)

        assertEquals(0, gateway.requests.last().cartEdit?.line)
        assertEquals(3, gateway.requests.last().cartEdit?.quantity)
        assertFalse(viewModel.state.value.canConfirm)
        viewModel.confirm("Sam", "555-0100", "")
        assertNull(gateway.placedWith)
    }

    @Test
    fun errorTurnOffersTheTouchMenuAndKeepsTheCart() {
        gateway.replies += turn(providerError)

        viewModel.send("a soda")

        val state = viewModel.state.value
        assertTrue(state.offerTouchMenu)
        assertEquals("Soda", state.cart?.lines?.single()?.name)
        assertFalse(state.canConfirm)
        assertFalse(state.isBusy)
    }

    @Test
    fun networkFailureOffersTheTouchMenuAndAllowsRetry() {
        gateway.failNext = IOException("no route to host")

        viewModel.send("a soda")

        assertTrue(viewModel.state.value.offerTouchMenu)
        assertFalse(viewModel.state.value.isBusy)

        gateway.replies += turn(confirmSoda)
        viewModel.send("a soda to the library")
        assertTrue(viewModel.state.value.canConfirm)
        assertFalse(viewModel.state.value.offerTouchMenu)
    }

    @Test
    fun rejectedOrderOffersTheTouchMenu() {
        gateway.replies += turn(confirmSoda)
        viewModel.send("a soda to the library")
        gateway.failNext = IOException("400: Soda is currently unavailable.")

        viewModel.confirm("Sam", "555-0100", "")

        val state = viewModel.state.value
        assertNull(state.placedOrderId)
        assertTrue(state.offerTouchMenu)
        assertFalse(state.canConfirm)
    }

    private class FakeGateway : AssistantGateway {
        val requests = mutableListOf<ParseOrderRequest>()
        val replies = ArrayDeque<AiParseOrderResponse>()
        var failNext: Exception? = null
        var placedWith: AiParseOrderResponse? = null

        private fun failIfAsked() {
            failNext?.let {
                failNext = null
                throw it
            }
        }

        override suspend fun sendTurn(request: ParseOrderRequest): AiParseOrderResponse {
            requests += request
            failIfAsked()
            return replies.removeFirst()
        }

        override suspend fun placeOrder(
            sessionId: String,
            confirmedTurn: AiParseOrderResponse,
            studentName: String,
            phone: String,
            email: String
        ): Int {
            failIfAsked()
            placedWith = confirmedTurn
            return 41
        }
    }
}
