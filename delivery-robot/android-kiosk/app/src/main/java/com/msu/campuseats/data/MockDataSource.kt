package com.msu.campuseats.data

import com.msu.campuseats.data.models.MenuItem
import com.msu.campuseats.data.models.Vendor

object MockDataSource {
    val vendors = listOf(
        Vendor("1", 1, "The Hawk's Nest Deli", "Deli", "15-20 min", true, "\uD83E\uDD6A", "Fresh deli classics made fast."),
        Vendor("2", 2, "Campus Grill", "American Grill", "20-25 min", true, "\uD83C\uDF54", "Burgers, fries, and comfort favorites."),
        Vendor("3", 3, "Green Bowl", "Healthy", "10-15 min", true, "\uD83E\uDD57", "Salads, bowls, and lighter options."),
        Vendor("4", 4, "Brew & Bites Cafe", "Cafe", "12-18 min", false, "\u2615", "Coffee, pastries, and quick bites.")
    )

    private val vendorMenus: Map<String, List<MenuItem>> = mapOf(
        "1" to listOf(
            MenuItem("11", 11, "1", 1, "The Hawk's Nest Deli", "Italian Hero", "Salami, ham, provolone, peppers", 9.49, "Popular"),
            MenuItem("12", 12, "1", 1, "The Hawk's Nest Deli", "Turkey Club", "Turkey, bacon, lettuce, tomato", 8.99, "Mains")
        ),
        "2" to listOf(
            MenuItem("21", 21, "2", 2, "Campus Grill", "Campus Smash Burger", "Double patty, cheddar, pickles", 11.49, "Popular"),
            MenuItem("22", 22, "2", 2, "Campus Grill", "Chicken Tenders Basket", "Crispy tenders with dipping sauce", 9.99, "Mains")
        )
    )

    val menuItems: List<MenuItem> = vendorMenus.values.flatten()

    fun getVendor(vendorId: String): Vendor? = vendors.find { it.id == vendorId }

    fun getMenuForVendor(vendorId: String): List<MenuItem> = vendorMenus[vendorId].orEmpty()
}
