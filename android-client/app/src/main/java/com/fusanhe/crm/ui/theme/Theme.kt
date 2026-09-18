package com.fusanhe.crm.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val GreenSecondary = Color(0xFF3F6353)

private val LightColors = lightColorScheme(
    primary = ForestGreen,
    onPrimary = Color.White,
    primaryContainer = ForestGreenContainer,
    onPrimaryContainer = OnForestGreenContainer,
    secondary = GreenSecondary,
    secondaryContainer = Color(0xFFD9E9E0),
    onSecondaryContainer = Color(0xFF10382A),
    background = LightBackground,
    onBackground = LightOnSurface,
    surface = LightSurface,
    onSurface = LightOnSurface,
    surfaceVariant = LightSurfaceVariant,
    onSurfaceVariant = LightOnSurfaceVariant,
    outline = LightOutline,
    error = RiskHigh,
)

// 深色主题预留：结构与浅色一致，可在设置中切换
private val DarkColors = darkColorScheme(
    primary = Color(0xFF8FD6B3),
    primaryContainer = DarkPrimaryContainer,
    onPrimaryContainer = DarkOnPrimaryContainer,
    background = DarkBackground,
    onBackground = Color(0xFFE2E5E2),
    surface = DarkSurface,
    onSurface = Color(0xFFE2E5E2),
    surfaceVariant = DarkSurfaceVariant,
    onSurfaceVariant = Color(0xFFBFC5BF),
    outline = DarkOutline,
)

/**
 * 应用主题：默认浅色（品牌森林绿），预留深色主题；
 * darkTheme 由设置页的"主题模式"决定。
 */
@Composable
fun FusanheTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = FusanheTypography,
        shapes = FusanheShapes,
        content = content,
    )
}
