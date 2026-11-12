package com.msu.campuseats.data.remote

import com.google.gson.annotations.SerializedName

data class TokenResponse(
    @SerializedName("access") val access: String,
    @SerializedName("refresh") val refresh: String
)

data class ParseOrderRequest(
    @SerializedName("session_id") val sessionId: String,
    @SerializedName("transcript") val transcript: String
)

data class AiDraftItem(
    @SerializedName("menuItemId") val menuItemId: String?,
    @SerializedName("name") val name: String,
    @SerializedName("quantity") val quantity: Int,
    @SerializedName("customizations") val customizations: List<String> = emptyList()
)

data class AiParseOrderResponse(
    @SerializedName("session_id") val sessionId: String,
    @SerializedName("action") val action: String,
    @SerializedName("items") val items: List<AiDraftItem> = emptyList(),
    @SerializedName("vendorId") val vendorId: Int?,
    @SerializedName("deliveryLocation") val deliveryLocation: String?,
    @SerializedName("clarificationNeeded") val clarificationNeeded: String?,
    @SerializedName("valid_for_submission") val validForSubmission: Boolean = false,
    @SerializedName("confirmation_token") val confirmationToken: String?
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

