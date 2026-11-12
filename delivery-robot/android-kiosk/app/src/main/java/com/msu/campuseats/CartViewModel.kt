package com.msu.campuseats

import androidx.lifecycle.ViewModel
import com.msu.campuseats.data.models.CartItem
import com.msu.campuseats.data.models.MenuItem
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlin.math.round

class CartViewModel : ViewModel() {
    private val _cartItems = MutableStateFlow<List<CartItem>>(emptyList())
    val cartItems: StateFlow<List<CartItem>> = _cartItems.asStateFlow()

    val subtotal = cartItems.map { items ->
        items.sumOf { it.menuItem.price * it.quantity }.round2()
    }

    val tax = subtotal.map { value ->
        (value * 0.08875).round2()
    }

    val total = subtotal.map { value ->
        (value * 1.08875).round2()
    }

    fun addItem(menuItem: MenuItem) {
        val existing = _cartItems.value.toMutableList()
        val index = existing.indexOfFirst { it.menuItem.id == menuItem.id }
        if (index >= 0) {
            existing[index] = existing[index].copy(quantity = existing[index].quantity + 1)
        } else {
            existing.add(CartItem(menuItem, 1))
        }
        _cartItems.value = existing
    }

    fun removeItem(menuItem: MenuItem) {
        val existing = _cartItems.value.toMutableList()
        val index = existing.indexOfFirst { it.menuItem.id == menuItem.id }
        if (index >= 0) {
            val current = existing[index]
            if (current.quantity <= 1) {
                existing.removeAt(index)
            } else {
                existing[index] = current.copy(quantity = current.quantity - 1)
            }
            _cartItems.value = existing
        }
    }

    fun updateQuantity(menuItem: MenuItem, qty: Int) {
        val existing = _cartItems.value.toMutableList()
        val index = existing.indexOfFirst { it.menuItem.id == menuItem.id }
        when {
            qty <= 0 && index >= 0 -> {
                existing.removeAt(index)
                _cartItems.value = existing
            }

            qty > 0 && index >= 0 -> {
                existing[index] = existing[index].copy(quantity = qty)
                _cartItems.value = existing
            }

            qty > 0 && index < 0 -> {
                existing.add(CartItem(menuItem, qty))
                _cartItems.value = existing
            }
        }
    }

    fun clearCart() {
        _cartItems.value = emptyList()
    }

    fun quantityFor(itemId: String): Int {
        return _cartItems.value.firstOrNull { it.menuItem.id == itemId }?.quantity ?: 0
    }

    fun cartVendorName(): String {
        return _cartItems.value.firstOrNull()?.menuItem?.vendorName ?: ""
    }

    fun currentCartItems(): List<CartItem> = _cartItems.value
}

private fun Double.round2(): Double = round(this * 100) / 100
