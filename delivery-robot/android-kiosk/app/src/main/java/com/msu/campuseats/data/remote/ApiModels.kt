package com.msu.campuseats.data.remote

import com.google.gson.annotations.SerializedName

data class TokenResponse(
    @SerializedName("access") val access: String,
    @SerializedName("refresh") val refresh: String
)

/** A tapped option, sent back exactly as the previous turn offered it. */
data class SelectedOption(
    @SerializedName("slot") val slot: String,
    @SerializedName("menuItemId") val menuItemId: String? = null,
    @SerializedName("value") val value: String? = null
)

/** A touch edit on the cart card; quantity 0 removes the line. */
data class CartEdit(
    @SerializedName("line") val line: Int,
    @SerializedName("quantity") val quantity: Int
)

/** One assistant turn. Exactly one of transcript, selectedOption, cartEdit is set. */
data class ParseOrderRequest(
    @SerializedName("session_id") val sessionId: String,
    @SerializedName("transcript") val transcript: String? = null,
    @SerializedName("selected_option") val selectedOption: SelectedOption? = null,
    @SerializedName("cart_edit") val cartEdit: CartEdit? = null
)

data class AiOption(
    @SerializedName("slot") val slot: String,
    @SerializedName("label") val label: String,
    @SerializedName("menuItemId") val menuItemId: String? = null,
    @SerializedName("value") val value: String? = null
)

data class AiCartItem(
    @SerializedName("line") val line: Int,
    @SerializedName("menuItemId") val menuItemId: String?,
    @SerializedName("name") val name: String,
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("customization") val customization: String? = null,
    @SerializedName("unitPrice") val unitPrice: String? = null
)

data class AiCart(
    @SerializedName("items") val items: List<AiCartItem>? = null,
    @SerializedName("vendorId") val vendorId: Int? = null,
    @SerializedName("vendorName") val vendorName: String? = null,
    @SerializedName("deliveryLocation") val deliveryLocation: String? = null
) {
    val lines: List<AiCartItem> get() = items.orEmpty()
}

// Gson leaves fields that are missing from the JSON as null whatever the Kotlin
// default says, so everything optional here is declared nullable.
data class AiParseOrderResponse(
    @SerializedName("action") val action: String?,
    @SerializedName("message") val message: String? = null,
    @SerializedName("options") val options: List<AiOption>? = null,
    @SerializedName("cart") val cart: AiCart? = null,
    @SerializedName("clarificationNeeded") val clarificationNeeded: String? = null,
    @SerializedName("valid_for_submission") val validForSubmission: Boolean = false,
    @SerializedName("confirmation_token") val confirmationToken: String? = null,
    @SerializedName("turn_id") val turnId: String? = null
)

data class VendorDto(
    @SerializedName("id") val id: Int,
    @SerializedName("name") val name: String,
    @SerializedName("location_label") val locationLabel: String,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("intake_paused") val intakePaused: Boolean
)

data class MenuItemDto(
    @SerializedName("id") val id: Int,
    @SerializedName("vendor") val vendor: Int,
    @SerializedName("name") val name: String,
    @SerializedName("description") val description: String,
    @SerializedName("price") val price: String,
    @SerializedName("is_available") val isAvailable: Boolean,
    @SerializedName("prep_time_minutes") val prepTimeMinutes: Int
)

data class CreateOrderItemRequest(
    @SerializedName("menu_item_id") val menuItemId: Int,
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("customization") val customization: String = ""
)

data class CreateOrderRequest(
    @SerializedName("student_name") val studentName: String,
    @SerializedName("phone") val phone: String,
    @SerializedName("vendor_id") val vendorId: Int,
    @SerializedName("delivery_location") val deliveryLocation: String,
    @SerializedName("items") val items: List<CreateOrderItemRequest>,
    @SerializedName("ai_session_id") val aiSessionId: String? = null,
    @SerializedName("confirmation_token") val confirmationToken: String? = null
)

data class CreateOrderResponse(
    @SerializedName("id") val id: Int,
    @SerializedName("status") val status: String
)

