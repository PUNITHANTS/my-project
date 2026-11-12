package com.msu.campuseats.ui.confirmation

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.msu.campuseats.data.models.CartItem
import com.msu.campuseats.ui.theme.kioskScale

@Composable
fun OrderConfirmationScreen(
    orderId: Int,
    vendorName: String,
    items: List<CartItem>,
    total: Double,
    location: String,
    onBackHome: () -> Unit
) {
    val scaleFactor = kioskScale()
    var animate by remember { mutableStateOf(false) }
    val scale by animateFloatAsState(targetValue = if (animate) 1f else 0.4f, animationSpec = spring())
    val steps = listOf("Order Received", "Preparing", "Ready", "On Its Way", "Delivered")

    LaunchedEffect(Unit) {
        animate = true
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding((20 * scaleFactor).dp),
        verticalArrangement = Arrangement.spacedBy((12 * scaleFactor).dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "\u2705",
            style = MaterialTheme.typography.displayLarge,
            modifier = Modifier.scale(scale)
        )
        Text("Order Placed!", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            text = "Order #$orderId",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )

        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 3.dp)
        ) {
            Column(modifier = Modifier.padding((16 * scaleFactor).dp), verticalArrangement = Arrangement.spacedBy((6 * scaleFactor).dp)) {
                Text("Vendor: $vendorName")
                Text("Delivery point: $location")
                Text("Estimated delivery: 20-25 minutes", fontWeight = FontWeight.SemiBold)
                Spacer(modifier = Modifier.height((4 * scaleFactor).dp))
                items.forEach {
                    Text("- ${it.menuItem.name} x${it.quantity}")
                }
                Spacer(modifier = Modifier.height((4 * scaleFactor).dp))
                Text("Total: $${"%.2f".format(total)}", fontWeight = FontWeight.Bold)
            }
        }

        Text("Order Status", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy((8 * scaleFactor).dp)
        ) {
            steps.forEachIndexed { index, label ->
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy((8 * scaleFactor).dp)) {
                    androidx.compose.foundation.Canvas(modifier = Modifier.size((14 * scaleFactor).dp)) {
                        drawCircle(color = if (index == 0) Color(0xFF0F766E) else Color.LightGray)
                    }
                    Text(label, fontWeight = if (index == 0) FontWeight.Bold else FontWeight.Normal)
                }
            }
        }

        Spacer(modifier = Modifier.weight(1f))
        Button(
            onClick = onBackHome,
            modifier = Modifier
                .fillMaxWidth()
                .height((60 * scaleFactor).dp),
            shape = CircleShape
        ) {
            Text("Back to Home")
        }
    }
}
