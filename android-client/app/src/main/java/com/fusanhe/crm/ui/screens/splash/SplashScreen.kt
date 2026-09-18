package com.fusanhe.crm.ui.screens.splash

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.fusanhe.crm.ui.components.FusanheLogoMark
import com.fusanhe.crm.ui.theme.FusanheTheme
import kotlinx.coroutines.delay

/**
 * 启动页：品牌展示 + 会话检查（演示：停留 1.2 秒后进入登录页或工作台）。
 */
@Composable
fun SplashScreen(
    isLoggedIn: Boolean,
    onNavigate: (loggedIn: Boolean) -> Unit,
) {
    LaunchedEffect(Unit) {
        delay(1200)
        onNavigate(isLoggedIn)
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        FusanheLogoMark(size = 88.dp)
        Spacer(Modifier.height(20.dp))
        Text(
            "福三和外贸 CRM",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            "客户 · 询盘 · AI 回复工作台",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(48.dp))
        Text(
            "UI 演示版 v0.1.0",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun SplashPreview() {
    FusanheTheme { SplashScreen(isLoggedIn = false, onNavigate = {}) }
}
