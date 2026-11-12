package com.msu.campuseats.ui.theme

import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalConfiguration

@Composable
fun kioskScale(): Float {
    val widthDp = LocalConfiguration.current.screenWidthDp
    return when {
        widthDp >= 1800 -> 1.5f
        widthDp >= 1400 -> 1.35f
        widthDp >= 1100 -> 1.2f
        else -> 1f
    }
}

