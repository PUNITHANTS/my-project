package com.msu.campuseats.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.msu.campuseats.data.models.MenuItem
import com.msu.campuseats.ui.theme.kioskScale

@Composable
fun MenuItemCard(
    menuItem: MenuItem,
    quantityInCart: Int,
    onAdd: () -> Unit,
    onIncrement: () -> Unit,
    onDecrement: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scale = kioskScale()
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape((12 * scale).dp),
        elevation = CardDefaults.cardElevation(defaultElevation = (3 * scale).dp)
    ) {
        Row(
            modifier = Modifier.padding((12 * scale).dp),
            horizontalArrangement = Arrangement.spacedBy((12 * scale).dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size((66 * scale).dp)
                    .background(Color(0xFFFFE0B2), RoundedCornerShape((8 * scale).dp))
            )
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy((4 * scale).dp)) {
                Text(text = menuItem.name, style = MaterialTheme.typography.titleSmall)
                Text(
                    text = menuItem.description,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(text = "$${"%.2f".format(menuItem.price)}", style = MaterialTheme.typography.labelLarge)
            }

            if (quantityInCart <= 0) {
                Button(
                    onClick = onAdd,
                    modifier = Modifier.defaultMinSize(minHeight = (56 * scale).dp),
                    shape = RoundedCornerShape((12 * scale).dp)
                ) {
                    Text("+ Add")
                }
            } else {
                QuantityStepper(
                    quantity = quantityInCart,
                    onDecrement = onDecrement,
                    onIncrement = onIncrement
                )
            }
        }
        Spacer(modifier = Modifier.height((4 * scale).dp))
    }
}
