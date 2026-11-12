package com.msu.campuseats.ui.cart

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.msu.campuseats.CartViewModel
import com.msu.campuseats.ui.components.QuantityStepper
import com.msu.campuseats.ui.theme.kioskScale
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CartScreen(
    cartViewModel: CartViewModel,
    onBack: () -> Unit,
    onBrowseMenu: () -> Unit,
    onPlaceOrder: suspend (location: String, name: String, phone: String, email: String) -> Boolean
) {
    val scale = kioskScale()
    val cartItems by cartViewModel.cartItems.collectAsState()
    val subtotal by cartViewModel.subtotal.collectAsState(0.0)
    val tax by cartViewModel.tax.collectAsState(0.0)
    val total by cartViewModel.total.collectAsState(0.0)
    var expanded by remember { mutableStateOf(false) }
    val locations = listOf("Student Center", "Student Rec Center", "Blanton Hall", "University Hall")
    var selectedLocation by remember { mutableStateOf("Select delivery point") }
    val vendorName = cartViewModel.cartVendorName().ifBlank { "Campus Eats" }
    val scope = rememberCoroutineScope()
    var isPlacingOrder by remember { mutableStateOf(false) }
    var placeOrderError by remember { mutableStateOf<String?>(null) }
    var guestName by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Your Cart")
                        Text(vendorName, style = MaterialTheme.typography.labelMedium)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        if (cartItems.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding((24 * scale).dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("\uD83D\uDED2", style = MaterialTheme.typography.displaySmall)
                Spacer(modifier = Modifier.height(8.dp))
                Text("Your cart is empty", style = MaterialTheme.typography.titleLarge)
                Spacer(modifier = Modifier.height((16 * scale).dp))
                Button(onClick = onBrowseMenu, modifier = Modifier.fillMaxWidth()) {
                    Text("Browse Menu")
                }
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding((16 * scale).dp)
            ) {
                LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy((10 * scale).dp)) {
                    items(cartItems) { cartItem ->
                        Card(
                            shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding((12 * scale).dp),
                                horizontalArrangement = Arrangement.spacedBy((12 * scale).dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(cartItem.menuItem.name, fontWeight = FontWeight.SemiBold)
                                    Text(cartItem.menuItem.description, style = MaterialTheme.typography.bodySmall)
                                    Text(
                                        "$${"%.2f".format(cartItem.menuItem.price * cartItem.quantity)}",
                                        style = MaterialTheme.typography.labelLarge
                                    )
                                }
                                QuantityStepper(
                                    quantity = cartItem.quantity,
                                    onDecrement = { cartViewModel.removeItem(cartItem.menuItem) },
                                    onIncrement = { cartViewModel.addItem(cartItem.menuItem) }
                                )
                                IconButton(onClick = { cartViewModel.updateQuantity(cartItem.menuItem, 0) }) {
                                    Icon(Icons.Default.Delete, contentDescription = "Remove")
                                }
                            }
                        }
                    }
                }

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = (3 * scale).dp)
                ) {
                    Column(modifier = Modifier.padding((16 * scale).dp), verticalArrangement = Arrangement.spacedBy((8 * scale).dp)) {
                        SummaryRow("Subtotal", subtotal)
                        SummaryRow("Estimated tax (8.875%)", tax)
                        SummaryRow("Total", total, true)
                        if (!placeOrderError.isNullOrBlank()) {
                            Text(
                                text = placeOrderError.orEmpty(),
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }

                        ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
                            OutlinedTextField(
                                value = selectedLocation,
                                onValueChange = {},
                                readOnly = true,
                                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .menuAnchor()
                            )
                            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                                locations.forEach { location ->
                                    DropdownMenuItem(
                                        text = { Text(location) },
                                        onClick = {
                                            selectedLocation = location
                                            expanded = false
                                        }
                                    )
                                }
                            }
                        }
                        OutlinedTextField(
                            value = guestName,
                            onValueChange = { guestName = it },
                            label = { Text("Name (optional)") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        OutlinedTextField(
                            value = phone,
                            onValueChange = { phone = it },
                            label = { Text("Phone") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        OutlinedTextField(
                            value = email,
                            onValueChange = { email = it },
                            label = { Text("Email") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Text(
                            text = "Phone or email is required.",
                            style = MaterialTheme.typography.bodySmall
                        )

                        Button(
                            onClick = {
                                scope.launch {
                                    isPlacingOrder = true
                                    placeOrderError = null
                                    val success = onPlaceOrder(
                                        selectedLocation,
                                        guestName.trim(),
                                        phone.trim(),
                                        email.trim()
                                    )
                                    if (!success) {
                                        placeOrderError = "Could not place order. Please try again."
                                    }
                                    isPlacingOrder = false
                                }
                            },
                            enabled = selectedLocation != "Select delivery point" &&
                                (phone.isNotBlank() || email.isNotBlank()) &&
                                !isPlacingOrder,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height((58 * scale).dp)
                        ) {
                            Text(if (isPlacingOrder) "Placing..." else "Place Order")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryRow(label: String, value: Double, emphasize: Boolean = false) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, fontWeight = if (emphasize) FontWeight.Bold else FontWeight.Normal)
        Text("$${"%.2f".format(value)}", fontWeight = if (emphasize) FontWeight.Bold else FontWeight.Normal)
    }
}
