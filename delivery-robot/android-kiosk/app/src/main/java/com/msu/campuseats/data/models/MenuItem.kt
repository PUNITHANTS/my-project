package com.msu.campuseats.data.models

data class MenuItem(
    val id: String,
    val backendId: Int,
    val vendorId: String,
    val vendorBackendId: Int,
    val vendorName: String,
    val name: String,
    val description: String,
    val price: Double,
    val category: String
)
