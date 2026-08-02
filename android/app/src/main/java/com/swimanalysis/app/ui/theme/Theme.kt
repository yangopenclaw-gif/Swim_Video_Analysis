package com.swimanalysis.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColorScheme = lightColorScheme(
    primary = PoolBlue,
    onPrimary = LaneWhite,
    primaryContainer = PoolBlueLight,
    onPrimaryContainer = PoolBlueDark,
    secondary = PoolBlueDark,
    onSecondary = LaneWhite,
    background = BgBackground,
    onBackground = TextPrimary,
    surface = BgSurface,
    onSurface = TextPrimary,
    error = StartRed,
    onError = LaneWhite
)

private val DarkColorScheme = darkColorScheme(
    primary = PoolBlueLight,
    onPrimary = PoolBlueDark,
    primaryContainer = PoolBlueDark,
    onPrimaryContainer = PoolBlueLight,
    secondary = PoolBlueLight,
    onSecondary = PoolBlueDark,
    background = Color(0xFF121212),
    onBackground = LaneWhite,
    surface = Color(0xFF1E1E1E),
    onSurface = LaneWhite,
    error = StartRed,
    onError = LaneWhite
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