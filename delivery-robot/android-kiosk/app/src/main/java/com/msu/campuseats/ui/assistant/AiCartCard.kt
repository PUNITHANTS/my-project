package com.msu.campuseats.ui.assistant

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.msu.campuseats.data.remote.AiCart
import com.msu.campuseats.ui.components.QuantityStepper
import java.util.Locale

/**
 * The assistant's cart. Edit turns each line into a stepper with a remove button;
 * every change goes to the backend as a cart edit, with no LLM call. Confirm asks
 * for contact details and places the order.
 */
@Composable
fun AiCartCard(
    cart: AiCart,
    canConfirm: Boolean,
    isBusy: Boolean,
    onEditLine: (line: Int, quantity: Int) -> Unit,
    onConfirm: (name: String, phone: String, email: String) -> Unit,
    modifier: Modifier = Modifier
) {
    var editing by rememberSaveable { mutableStateOf(false) }
    var enteringContact by rememberSaveable { mutableStateOf(false) }
    var studentName by rememberSaveable { mutableStateOf("") }
    var phone by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("Your order", style = MaterialTheme.typography.titleMedium)
            cart.vendorName?.let { Text("From $it", style = MaterialTheme.typography.bodyMedium) }

            cart.lines.forEach { line ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            if (editing) line.name else "${line.quantity} x ${line.name}",
                            fontWeight = FontWeight.Medium
                        )
                        if (!line.customization.isNullOrBlank()) {
                            Text(line.customization, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    if (editing) {
                        QuantityStepper(
                            quantity = line.quantity,
                            onDecrement = { if (!isBusy) onEditLine(line.line, line.quantity - 1) },
                            onIncrement = { if (!isBusy) onEditLine(line.line, line.quantity + 1) }
                        )
                        IconButton(onClick = { onEditLine(line.line, 0) }, enabled = !isBusy) {
                            Icon(Icons.Default.Delete, contentDescription = "Remove ${line.name}")
                        }
                    }
                }
            }

            Text(
                "Deliver to: " + (cart.deliveryLocation?.takeIf { it.isNotBlank() } ?: "not chosen yet")
            )
            estimatedSubtotal(cart)?.let {
                Text("Estimated subtotal: $it", style = MaterialTheme.typography.bodyMedium)
            }
            Text(
                "Prices and availability are checked again when the order is placed.",
                style = MaterialTheme.typography.bodySmall
            )

            if (enteringContact && canConfirm && !editing) {
                OutlinedTextField(
                    value = studentName,
                    onValueChange = { studentName = it },
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
                    label = { Text("Email (if no phone)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        editing = !editing
                        enteringContact = false
                    },
                    enabled = !isBusy,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 56.dp)
                ) {
                    Text(if (editing) "Done editing" else "Edit")
                }
                val readyToPlace = enteringContact && (phone.isNotBlank() || email.isNotBlank())
                Button(
                    onClick = {
                        if (enteringContact) onConfirm(studentName, phone, email)
                        else enteringContact = true
                    },
                    enabled = canConfirm && !isBusy && !editing && (!enteringContact || readyToPlace),
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 56.dp)
                ) {
                    Text(
                        when {
                            isBusy -> "Working..."
                            enteringContact -> "Place order"
                            else -> "Confirm"
                        }
                    )
                }
            }
            if (!canConfirm && !isBusy) {
                Text(
                    "Answer the question above to finish this order.",
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (enteringContact && !editing) {
                Text(
                    "Enter a phone number or email so we can reach you about the delivery.",
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

/** Null unless every line has a price, so a partial sum is never shown as the total. */
private fun estimatedSubtotal(cart: AiCart): String? {
    val prices = cart.lines.map { line ->
        (line.unitPrice?.toDoubleOrNull() ?: return null) * line.quantity
    }
    if (prices.isEmpty()) return null
    return String.format(Locale.US, "$%.2f", prices.sum())
}
