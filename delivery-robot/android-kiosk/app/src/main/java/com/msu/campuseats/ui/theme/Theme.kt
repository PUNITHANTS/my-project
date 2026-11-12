package com.msu.campuseats.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val LightColors = lightColorScheme(
    primary = Color(0xFF0F766E),
    secondary = Color(0xFF2A9D8F),
    tertiary = Color(0xFFFF6F00),
    surface = Color.White,
    background = Color(0xFFF9FAFB)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF70C1B3),
    secondary = Color(0xFF4AAE9B),
    tertiary = Color(0xFFFFB74D)
)

@Composable
fun CampusEatsTheme(content: @Composable () -> Unit) {
    val widthDp = LocalConfiguration.current.screenWidthDp
    val typography = when {
        widthDp >= 1400 -> Typography(
            headlineMedium = TextStyle(fontSize = 36.sp, fontWeight = FontWeight.Bold),
            headlineSmall = TextStyle(fontSize = 30.sp, fontWeight = FontWeight.Bold),
            titleLarge = TextStyle(fontSize = 26.sp, fontWeight = FontWeight.SemiBold),
            titleMedium = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.SemiBold),
            titleSmall = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.Medium),
            bodyLarge = TextStyle(fontSize = 20.sp),
            bodyMedium = TextStyle(fontSize = 18.sp),
            bodySmall = TextStyle(fontSize = 16.sp),
            labelLarge = TextStyle(fontSize = 18.sp, fontWeight = FontWeight.Medium),
            labelMedium = TextStyle(fontSize = 16.sp),
            labelSmall = TextStyle(fontSize = 14.sp),
            displaySmall = TextStyle(fontSize = 44.sp, fontWeight = FontWeight.Bold),
            displayLarge = TextStyle(fontSize = 60.sp, fontWeight = FontWeight.Bold)
        )
        else -> MaterialTheme.typography
    }

    MaterialTheme(
        colorScheme = LightColors,
        typography = typography,
        content = content
    )
}
