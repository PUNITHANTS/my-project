package com.msu.campuseats.data.remote

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface CampusEatsApi {
    @POST("/api/auth/token/")
    suspend fun login(@Body request: Map<String, String>): TokenResponse

    @POST("/api/ai/parse-order/")
    suspend fun parseOrderTurn(@Body request: ParseOrderRequest): AiParseOrderResponse

    @GET("/api/vendors/")
    suspend fun getVendors(): List<VendorDto>

    @GET("/api/menu/items/")
    suspend fun getMenuItems(): List<MenuItemDto>

    @POST("/api/orders/")
    suspend fun createOrder(@Body request: CreateOrderRequest): CreateOrderResponse
}

