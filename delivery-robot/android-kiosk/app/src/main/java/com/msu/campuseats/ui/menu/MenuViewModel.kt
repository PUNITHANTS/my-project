package com.msu.campuseats.ui.menu

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.msu.campuseats.data.BackendRepository
import com.msu.campuseats.data.models.MenuItem
import com.msu.campuseats.data.models.Vendor
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class MenuViewModel : ViewModel() {
    private val _selectedCategory = MutableStateFlow("Menu")
    val selectedCategory: StateFlow<String> = _selectedCategory.asStateFlow()

    private val _vendor = MutableStateFlow<Vendor?>(null)
    val vendor: StateFlow<Vendor?> = _vendor.asStateFlow()

    private val _menuItems = MutableStateFlow<List<MenuItem>>(emptyList())
    val menuItems: StateFlow<List<MenuItem>> = _menuItems.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    fun setCategory(category: String) {
        _selectedCategory.value = category
    }

    fun loadVendorMenu(vendorId: String) {
        val parsedId = vendorId.toIntOrNull() ?: return
        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            runCatching {
                val vendors = BackendRepository.getVendors()
                val selectedVendor = vendors.firstOrNull { it.backendId == parsedId }
                selectedVendor to BackendRepository.getMenuForVendor(parsedId, selectedVendor?.name ?: "Campus Eats")
            }.onSuccess { (vendor, items) ->
                _vendor.value = vendor
                _menuItems.value = items
            }.onFailure {
                _error.value = "Could not load menu for this vendor."
            }
            _isLoading.value = false
        }
    }

    fun categoriesForItems(items: List<MenuItem>): List<String> {
        val categories = items.map { it.category }.distinct()
        return if (categories.isEmpty()) listOf("Menu") else categories
    }
}
