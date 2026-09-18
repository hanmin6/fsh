package com.fusanhe.crm.ui.screens.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.DemoFlag
import com.fusanhe.crm.domain.model.ThemeMode

/**
 * 设置页：主题模式、演示控制开关（模拟失败/离线）、API 信息、关于。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val themeMode by viewModel.themeMode.collectAsStateWithLifecycle()
    val demoFlags by viewModel.demoFlags.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("设置") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
        ) {
            SettingsCard("外观") {
                Text("主题模式", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ThemeMode.entries.forEach { mode ->
                        FilterChip(
                            selected = themeMode == mode,
                            onClick = { viewModel.setThemeMode(mode) },
                            label = { Text(mode.label) },
                        )
                    }
                }
                Spacer(Modifier.height(6.dp))
                Text(
                    "深色主题为预留能力，当前以浅色为主",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }

            SettingsCard("演示控制（不影响真实系统）") {
                DemoSwitchRow(
                    title = "模拟网络加载失败",
                    subtitle = "刷新客户/询盘列表时返回错误",
                    checked = demoFlags.networkFailure,
                    onChange = { viewModel.setDemoFlag(DemoFlag.NETWORK_FAILURE, it) },
                )
                DemoSwitchRow(
                    title = "模拟翻译失败",
                    subtitle = "翻译请求返回失败，可演示重试",
                    checked = demoFlags.translationFailure,
                    onChange = { viewModel.setDemoFlag(DemoFlag.TRANSLATION_FAILURE, it) },
                )
                DemoSwitchRow(
                    title = "模拟发送失败",
                    subtitle = "发送消息时演示失败状态",
                    checked = demoFlags.sendFailure,
                    onChange = { viewModel.setDemoFlag(DemoFlag.SEND_FAILURE, it) },
                )
                DemoSwitchRow(
                    title = "模拟保存客户失败",
                    subtitle = "新增客户提交时演示失败",
                    checked = demoFlags.saveCustomerFailure,
                    onChange = { viewModel.setDemoFlag(DemoFlag.SAVE_FAILURE, it) },
                )
                DemoSwitchRow(
                    title = "模拟离线",
                    subtitle = "展示离线提示条并阻止加载",
                    checked = demoFlags.offline,
                    onChange = { viewModel.setDemoFlag(DemoFlag.OFFLINE, it) },
                )
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("演示数据操作", style = MaterialTheme.typography.bodyMedium)
                    Row {
                        TextButton(onClick = {
                            viewModel.simulateIncoming { name ->
                            }
                        }) { Text("模拟新消息") }
                        TextButton(onClick = {
                            viewModel.clearChatDrafts {
                            }
                        }) { Text("清空会话草稿") }
                    }
                }
            }

            SettingsCard("API 与数据") {
                InfoLine("API 地址", "http://localhost:8080/api/v1")
                InfoLine("运行模式", "UI 演示（Mock 数据，不连接真实数据库）")
                InfoLine("本地缓存", "Room 已定义占位，暂未启用")
            }

            SettingsCard("关于") {
                InfoLine("应用版本", "0.1.0-demo")
                InfoLine("应用名称", "福三和外贸 CRM")
                Text(
                    "本应用当前仅用于界面与交互演示，不会发送任何真实消息，也不包含任何数据库密码、API Key 或 Token。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun SettingsCard(title: String, content: @Composable () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 12.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun DemoSwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onChange(!checked) }
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium)
            Text(
                subtitle,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun InfoLine(label: String, value: String) {
    Row(Modifier.padding(vertical = 3.dp)) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(84.dp),
        )
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}
