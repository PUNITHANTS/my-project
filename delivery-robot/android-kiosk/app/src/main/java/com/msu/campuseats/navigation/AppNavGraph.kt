package com.msu.campuseats.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.msu.campuseats.CartViewModel
import com.msu.campuseats.data.BackendRepository
import com.msu.campuseats.data.models.CartItem
import com.msu.campuseats.data.models.MenuItem
import com.msu.campuseats.data.remote.AiCart
import com.msu.campuseats.ui.assistant.AssistantScreen
import com.msu.campuseats.ui.cart.CartScreen
import com.msu.campuseats.ui.confirmation.OrderConfirmationScreen
import com.msu.campuseats.ui.home.HomeScreen
import com.msu.campuseats.ui.menu.MenuScreen
import java.net.URLDecoder
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

object AppRoutes {
    const val HOME = "home"
    const val MENU = "menu/{vendorId}"
    const val CART = "cart"
    const val ASSISTANT = "assistant"
    const val CONFIRMATION = "confirmation/{orderId}/{location}"
}

@Composable
fun AppNavGraph(cartViewModel: CartViewModel) {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = AppRoutes.HOME) {
        composable(AppRoutes.HOME) {
            HomeScreen(
                cartViewModel = cartViewModel,
                onVendorClick = { vendorId -> navController.navigate("menu/$vendorId") },
                onCartClick = { navController.navigate(AppRoutes.CART) },
                onAssistantClick = { navController.navigate(AppRoutes.ASSISTANT) }
            )
        }

        composable(AppRoutes.ASSISTANT) {
            AssistantScreen(
                onBack = { navController.popBackStack() },
                onUseTouchMenu = { aiCart ->
                    // Fallback: carry the assistant's items into the touch cart so the
                    // customer does not start over, then leave the assistant.
                    val carried = aiCart?.toTouchCartItems().orEmpty()
                    if (carried.isEmpty()) {
                        navController.popBackStack(AppRoutes.HOME, inclusive = false)
                    } else {
                        cartViewModel.clearCart()
                        carried.forEach { cartViewModel.updateQuantity(it.menuItem, it.quantity) }
                        navController.navigate(AppRoutes.CART) {
                            popUpTo(AppRoutes.HOME)
                        }
                    }
                },
                onOrderPlaced = { navController.popBackStack(AppRoutes.HOME, inclusive = false) }
            )
        }

        composable(
            route = AppRoutes.MENU,
            arguments = listOf(navArgument("vendorId") { type = NavType.StringType })
        ) { backStack ->
            val vendorId = backStack.arguments?.getString("vendorId").orEmpty()
            MenuScreen(
                vendorId = vendorId,
                cartViewModel = cartViewModel,
                onBack = { navController.popBackStack() },
                onCartClick = { navController.navigate(AppRoutes.CART) }
            )
        }

        composable(AppRoutes.CART) {
            CartScreen(
                cartViewModel = cartViewModel,
                onBack = { navController.popBackStack() },
                onBrowseMenu = { navController.popBackStack() },
                onPlaceOrder = { location, name, phone, email ->
                    val cartItems = cartViewModel.currentCartItems()
                    val orderId = BackendRepository.placeOrder(
                        cartItems = cartItems,
                        location = location,
                        studentName = name,
                        phone = phone,
                        email = email
                    )
                    if (orderId == null) {
                        false
                    } else {
                        val encoded = URLEncoder.encode(location, StandardCharsets.UTF_8.toString())
                        navController.navigate("confirmation/$orderId/$encoded")
                        true
                    }
                }
            )
        }

        composable(
            route = AppRoutes.CONFIRMATION,
            arguments = listOf(
                navArgument("orderId") { type = NavType.IntType },
                navArgument("location") { type = NavType.StringType },
            ),
        ) { backStack ->
            val items by cartViewModel.cartItems.collectAsState()
            val total by cartViewModel.total.collectAsState(0.0)
            val orderId = backStack.arguments?.getInt("orderId") ?: 0
            val location = URLDecoder.decode(
                backStack.arguments?.getString("location").orEmpty(),
                StandardCharsets.UTF_8.toString()
            )
            val vendorName = cartViewModel.cartVendorName().ifBlank { "Campus Eats" }
            OrderConfirmationScreen(
                orderId = orderId,
                vendorName = vendorName,
                items = items,
                total = total,
                location = location,
                onBackHome = {
                    cartViewModel.clearCart()
                    navController.navigate(AppRoutes.HOME) {
                        popUpTo(AppRoutes.HOME) { inclusive = true }
                        launchSingleTop = true
                    }
                }
            )
        }
    }
}

/**
 * The assistant's cart as touch-cart items. The touch cart holds one line per menu
 * item and no customizations, so duplicate lines are merged and options are dropped.
 */
private fun AiCart.toTouchCartItems(): List<CartItem> {
    val vendor = vendorId ?: return emptyList()
    return lines
        .filter { it.menuItemId?.toIntOrNull() != null }
        .groupBy { it.menuItemId!!.toInt() }
        .map { (backendId, sameItem) ->
            val first = sameItem.first()
            CartItem(
                menuItem = MenuItem(
                    id = backendId.toString(),
                    backendId = backendId,
                    vendorId = vendor.toString(),
                    vendorBackendId = vendor,
                    vendorName = vendorName.orEmpty(),
                    name = first.name,
                    description = "",
                    price = first.unitPrice?.toDoubleOrNull() ?: 0.0,
                    category = "Menu"
                ),
                quantity = sameItem.sumOf { it.quantity }
            )
        }
}
