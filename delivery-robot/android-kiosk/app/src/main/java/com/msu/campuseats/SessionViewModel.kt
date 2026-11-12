package com.msu.campuseats

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.msu.campuseats.data.BackendRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SessionViewModel : ViewModel() {
    private val _isAuthenticated = MutableStateFlow(BackendRepository.isAuthenticated())
    val isAuthenticated: StateFlow<Boolean> = _isAuthenticated.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    init {
        bootstrapSession()
    }

    private fun bootstrapSession() {
        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            val ok = BackendRepository.bootstrapKioskSession()
            _isAuthenticated.value = ok
            if (!ok) _error.value = "Kiosk service is unavailable. Please contact staff."
            _isLoading.value = false
        }
    }
}

