package com.msu.campuseats.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.msu.campuseats.data.models.Vendor
import com.msu.campuseats.ui.theme.kioskScale

@Composable
fun VendorCard(vendor: Vendor, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val scale = kioskScale()
    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape((12 * scale).dp),
        elevation = CardDefaults.cardElevation(defaultElevation = (3 * scale).dp)
    ) {
        Column(modifier = Modifier.padding((16 * scale).dp), verticalArrangement = Arrangement.spacedBy((8 * scale).dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .background(Color(0xFFFFF3E0), RoundedCornerShape((10 * scale).dp))
                        .padding(horizontal = (12 * scale).dp, vertical = (8 * scale).dp)
                ) {
                    Text(text = vendor.emoji)
                }
                Spacer(modifier = Modifier.weight(1f))
                AssistChip(
                    onClick = { },
                    label = { Text(if (vendor.isOpen) "Open" else "Closed") },
                    enabled = vendor.isOpen
                )
            }

            Text(text = vendor.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Row(horizontalArrangement = Arrangement.spacedBy((8 * scale).dp)) {
                Text(text = vendor.cuisine, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                Text(text = vendor.estimatedTime, style = MaterialTheme.typography.labelMedium)
            }
            Spacer(modifier = Modifier.height((2 * scale).dp))
        }
    }
}
