package com.msu.campuseats.ui.assistant

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.msu.campuseats.data.BackendRepository
import com.msu.campuseats.data.remote.AiCart
import com.msu.campuseats.data.remote.AiOption
import com.msu.campuseats.data.remote.AiParseOrderResponse
import com.msu.campuseats.data.remote.CartEdit
import com.msu.campuseats.data.remote.ParseOrderRequest
import com.msu.campuseats.data.remote.SelectedOption
import java.util.Locale
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import retrofit2.HttpException

enum class ChatRole { USER, ASSISTANT }

data class ChatMessage(val role: ChatRole, val text: String)

data class AssistantUiState(
    val messages: List<ChatMessage> = listOf(ChatMessage(ChatRole.ASSISTANT, GREETING)),
    /** Answers to the latest question; tapping one needs no typing and no LLM call. */
    val options: List<AiOption> = emptyList(),
    val cart: AiCart? = null,
    /** True only while the backend holds a confirmation for exactly this cart. */
    val canConfirm: Boolean = false,
    val isBusy: Boolean = false,
    /** Set when the assistant cannot continue, so the screen offers the touch menu. */
    val offerTouchMenu: Boolean = false,
    val placedOrderId: Int? = null
) {
    val hasCartItems: Boolean get() = cart?.lines?.isNotEmpty() == true
}

/** The two backend calls the assistant makes; replaced by a fake in unit tests. */
interface AssistantGateway {
    suspend fun sendTurn(request: ParseOrderRequest): AiParseOrderResponse

    suspend fun placeOrder(
        sessionId: String,
        confirmedTurn: AiParseOrderResponse,
        studentName: String,
        phone: String,
        email: String
    ): Int
}

private object BackendAssistantGateway : AssistantGateway {
    override suspend fun sendTurn(request: ParseOrderRequest) =
        BackendRepository.sendAssistantTurn(request)

    override suspend fun placeOrder(
        sessionId: String,
        confirmedTurn: AiParseOrderResponse,
        studentName: String,
        phone: String,
        email: String
    ) = BackendRepository.placeAiOrder(sessionId, confirmedTurn, studentName, phone, email)
}

class AssistantViewModel(
    private val gateway: AssistantGateway = BackendAssistantGateway
) : ViewModel() {
    private val sessionId = UUID.randomUUID().toString()
    private val _state = MutableStateFlow(AssistantUiState())
    val state: StateFlow<AssistantUiState> = _state.asStateFlow()

    /** The latest CONFIRM turn; its token is what authorizes placing the order. */
    private var confirmedTurn: AiParseOrderResponse? = null

    fun send(text: String) {
        val transcript = text.trim()
        if (transcript.isEmpty() || !acceptsInput()) return
        addMessage(ChatRole.USER, transcript)
        runTurn(ParseOrderRequest(sessionId = sessionId, transcript = transcript))
    }

    fun selectOption(option: AiOption) {
        if (!acceptsInput()) return
        addMessage(ChatRole.USER, option.label)
        runTurn(
            ParseOrderRequest(
                sessionId = sessionId,
                selectedOption = SelectedOption(option.slot, option.menuItemId, option.value)
            )
        )
    }

    /** Sets a cart line's quantity; 0 removes the line. */
    fun editLine(line: Int, quantity: Int) {
        if (!acceptsInput() || quantity < 0) return
        runTurn(ParseOrderRequest(sessionId = sessionId, cartEdit = CartEdit(line, quantity)))
    }

    fun confirm(studentName: String, phone: String, email: String) {
        val turn = confirmedTurn
        if (!acceptsInput() || turn == null || !_state.value.canConfirm) return
        _state.update { it.copy(isBusy = true) }
        viewModelScope.launch {
            try {
                val orderId = gateway.placeOrder(
                    sessionId, turn, studentName.trim(), phone.trim(), email.trim()
                )
                _state.update {
                    it.copy(isBusy = false, canConfirm = false, options = emptyList(), placedOrderId = orderId)
                }
                addMessage(ChatRole.ASSISTANT, "Order #$orderId was placed. Thank you!")
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // The backend re-checks the cart against the live menu here, so a
                // rejection usually means an item or option changed mid-conversation.
                confirmedTurn = null
                _state.update { it.copy(isBusy = false, canConfirm = false, offerTouchMenu = true) }
                addMessage(
                    ChatRole.ASSISTANT,
                    "The order was not placed. The menu may have changed, or the confirmation " +
                        "expired. Tell me what to change, or order from the menu."
                )
            }
        }
    }

    private fun acceptsInput(): Boolean =
        !_state.value.isBusy && _state.value.placedOrderId == null

    private fun runTurn(request: ParseOrderRequest) {
        // Any new turn can change the cart, so the previous confirmation is void.
        confirmedTurn = null
        _state.update { it.copy(isBusy = true, canConfirm = false, options = emptyList()) }
        viewModelScope.launch {
            try {
                show(gateway.sendTurn(request))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                val expiredChoice = error is HttpException && error.code() == 400
                _state.update { it.copy(isBusy = false, offerTouchMenu = !expiredChoice || it.offerTouchMenu) }
                addMessage(
                    ChatRole.ASSISTANT,
                    if (expiredChoice) {
                        "That choice is no longer available. Please tell me again what you would like."
                    } else {
                        "I could not reach the ordering assistant. You can try again or order from the menu."
                    }
                )
            }
        }
    }

    private fun show(turn: AiParseOrderResponse) {
        val action = turn.action.orEmpty().uppercase(Locale.ROOT)
        val cart = turn.cart
        val text = turn.message?.takeIf { it.isNotBlank() }
            ?: turn.clarificationNeeded?.takeIf { it.isNotBlank() }
        when (action) {
            "ASK", "REPAIR" -> {
                _state.update {
                    it.copy(isBusy = false, cart = cart, options = turn.options.orEmpty(), offerTouchMenu = false)
                }
                addMessage(ChatRole.ASSISTANT, text ?: "Could you tell me a bit more about your order?")
            }

            "CONFIRM" -> {
                val ready = turn.validForSubmission &&
                    !turn.confirmationToken.isNullOrBlank() &&
                    cart?.vendorId != null &&
                    !cart.deliveryLocation.isNullOrBlank() &&
                    cart.lines.isNotEmpty()
                confirmedTurn = turn.takeIf { ready }
                _state.update {
                    it.copy(isBusy = false, cart = cart, canConfirm = ready, offerTouchMenu = !ready)
                }
                addMessage(
                    ChatRole.ASSISTANT,
                    if (ready) {
                        "Here is your order. Check it, then confirm or edit it."
                    } else {
                        "I could not prepare this order safely. Please order from the menu."
                    }
                )
            }

            // ERROR, ESCALATE and anything unknown: stop asking and offer the touch menu.
            else -> {
                _state.update {
                    it.copy(isBusy = false, cart = cart ?: it.cart, offerTouchMenu = true)
                }
                addMessage(
                    ChatRole.ASSISTANT,
                    text ?: "The ordering assistant is unavailable right now. Please order from the menu."
                )
            }
        }
    }

    private fun addMessage(role: ChatRole, text: String) {
        _state.update { current ->
            // A cart edit often returns the same prompt again; do not repeat it.
            val repeated = role == ChatRole.ASSISTANT &&
                current.messages.lastOrNull() == ChatMessage(role, text)
            if (repeated) current
            else current.copy(messages = current.messages + ChatMessage(role, text))
        }
    }
}

const val GREETING = "Tell me what you would like to order and where it should be delivered."
