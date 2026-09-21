package com.swimanalysis.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = WarmCoral,
    onPrimary = Color.White,
    primaryContainer = WarmCoralLight,
    onPrimaryContainer = WarmCoralDark,
    secondary = WarmGold,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFE8C7),
    onSecondaryContainer = Color(0xFF7A4A00),
    tertiary = WarmRose,
    onTertiary = Color.White,
    background = BgBackground,
    onBackground = TextPrimary,
    surface = BgSurface,
    onSurface = TextPrimary,
    surfaceVariant = CreamVariant,
    onSurfaceVariant = TextSecondary,
    error = Color(0xFFD32F2F),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    outline = Color(0xFFB8A79E),
    outlineVariant = Color(0xFFE8D9CF)
)

private val DarkColorScheme = darkColorScheme(
    primary = DarkCoral,
    onPrimary = Color(0xFF5A1F0A),
    primaryContainer = WarmCoralDark,
    onPrimaryContainer = WarmCoralLight,
    secondary = WarmGold,
    onSecondary = Color(0xFF4A2C00),
    secondaryContainer = Color(0xFF6B4A00),
    onSecondaryContainer = Color(0xFFFFE8C7),
    tertiary = WarmRose,
    onTertiary = Color(0xFF5A1F0A),
    background = DarkBackground,
    onBackground = Color(0xFFF3E7E0),
    surface = DarkSurface,
    onSurface = Color(0xFFF3E7E0),
    surfaceVariant = Color(0xFF3A2E28),
    onSurfaceVariant = Color(0xFFD4BCB0),
    error = Color(0xFFEF9A9A),
    onError = Color(0xFF4A0A0A),
    errorContainer = Color(0xFF5C1A1A),
    onErrorContainer = Color(0xFFFFDAD6),
    outline = Color(0xFF8D7B72),
    outlineVariant = Color(0xFF4A3A32)
)

@Composable
fun SwimAnalysisTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme,
        typography = SwimTypography,
        content = content
    )
}
