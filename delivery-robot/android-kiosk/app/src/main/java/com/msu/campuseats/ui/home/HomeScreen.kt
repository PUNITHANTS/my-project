package com.msu.campuseats.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.msu.campuseats.CartViewModel
import com.msu.campuseats.ui.components.AiChatBottomSheet
import com.msu.campuseats.ui.components.AiChatFab
import com.msu.campuseats.ui.components.CartFab
import com.msu.campuseats.ui.components.VendorCard
import com.msu.campuseats.ui.theme.kioskScale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    cartViewModel: CartViewModel,
    onVendorClick: (String) -> Unit,
    onCartClick: () -> Unit
) {
    val scale = kioskScale()
    val homeViewModel: HomeViewModel = viewModel()
    val vendors by homeViewModel.vendors.collectAsState()
    val isLoading by homeViewModel.isLoading.collectAsState()
    val error by homeViewModel.error.collectAsState()
    val vendorNames = remember(vendors) { vendors.associate { it.backendId to it.name } }
    val cartItems by cartViewModel.cartItems.collectAsState()
    val total by cartViewModel.total.collectAsState(0.0)
    var showAiChat by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("Campus Eats", fontWeight = FontWeight.Bold)
                        Text("\uD83C\uDF93")
                    }
                }
            )
        },
        floatingActionButton = {
            Column(verticalArrangement = Arrangement.spacedBy((12 * scale).dp)) {
                AiChatFab(onClick = { showAiChat = true })
                CartFab(
                    itemCount = cartItems.sumOf { it.quantity },
                    total = total,
                    onClick = onCartClick
                )
            }
        }
    ) { padding ->
        if (showAiChat) {
            AiChatBottomSheet(
                onDismiss = { showAiChat = false },
                vendorNames = vendorNames
            )
        }
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues((16 * scale).dp),
            verticalArrangement = Arrangement.spacedBy((12 * scale).dp)
        ) {
            item {
                OutlinedTextField(
                    value = "",
                    onValueChange = {},
                    readOnly = true,
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    placeholder = { Text("Search restaurants or items") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
            item {
                Text(
                    text = "Restaurants & Vendors",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
            if (isLoading) {
                item {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
            if (!error.isNullOrBlank()) {
                item {
                    Text(
                        text = error.orEmpty(),
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }
            items(vendors) { vendor ->
                VendorCard(
                    vendor = vendor,
                    onClick = { onVendorClick(vendor.id) }
                )
            }
        }
    }
}
