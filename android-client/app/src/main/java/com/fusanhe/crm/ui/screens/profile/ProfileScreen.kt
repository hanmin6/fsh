package com.fusanhe.crm.ui.screens.profile

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Help
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Campaign
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Verified
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.ui.components.AvatarInitials
import com.fusanhe.crm.ui.components.ConfirmDialog
import com.fusanhe.crm.ui.components.StatTile
import com.fusanhe.crm.ui.theme.FusanheTheme
import com.fusanhe.crm.ui.theme.RiskHigh

/**
 * 我的页面：个人资料、统计、功能入口、退出登录。
 */
@Composable
fun ProfileScreen(
    onOpenSettings: () -> Unit,
    onOpenNotifications: () -> Unit,
    onLogout: () -> Unit,
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val showLogoutDialog by viewModel.showLogoutDialog.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(bottom = 24.dp),
    ) {
        Text(
            "我的",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
        )

        // 个人资料卡
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
        ) {
            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                AvatarInitials(state.userName, size = 56.dp)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        state.userName,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "${state.role} · ${state.department}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        state.company,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
            }
        }

        // 统计
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatTile(
                label = "本月新增客户",
                value = "${state.stats.newCustomersThisMonth}",
                valueColor = MaterialTheme.colorScheme.primary,
                modifier = Modifier.weight(1f),
            )
            StatTile(
                label = "跟进中询盘",
                value = "${state.stats.activeInquiries}",
                valueColor = com.fusanhe.crm.ui.theme.StatusWaiting,
                modifier = Modifier.weight(1f),
            )
            StatTile(
                label = "演示模式",
                value = "开启",
                valueColor = com.fusanhe.crm.ui.theme.StatusInfo,
                modifier = Modifier.weight(1f),
            )
        }

        // 功能入口
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
        ) {
            Column {
                ProfileMenuItem(Icons.Outlined.Person, "个人资料") {
                    // 演示：无编辑功能
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                ProfileMenuItem(Icons.Outlined.Settings, "我的设置", onOpenSettings)
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                ProfileMenuItem(Icons.Outlined.Campaign, "通知与异常", onOpenNotifications)
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                ProfileMenuItem(Icons.Outlined.Verified, "知识资料库") {
                    // 演示：知识库在 AI 建议中引用
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                ProfileMenuItem(Icons.AutoMirrored.Outlined.Help, "帮助与反馈") {
                    // 演示：占位入口
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                ProfileMenuItem(Icons.Outlined.Info, "关于福三和 CRM") {
                    // 演示：版本信息见设置页
                }
            }
        }

        Spacer(Modifier.height(16.dp))
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "v1.0.0 · UI 演示版，数据为本地 Mock",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }

        Spacer(Modifier.height(16.dp))
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { viewModel.showLogoutConfirm() }
                    .padding(16.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.AutoMirrored.Outlined.Logout,
                    contentDescription = null,
                    tint = RiskHigh,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text("退出登录", color = RiskHigh, fontWeight = FontWeight.Medium)
            }
        }
    }

    if (showLogoutDialog) {
        ConfirmDialog(
            title = "退出登录",
            text = "确定要退出当前账号吗？（演示模式：仅返回登录页）",
            confirmText = "退出",
            isError = true,
            onConfirm = {
                viewModel.dismissLogoutDialog()
                viewModel.logout()
                onLogout()
            },
            onDismiss = viewModel::dismissLogoutDialog,
        )
    }
}

@Composable
private fun ProfileMenuItem(
    icon: ImageVector,
    title: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            icon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(20.dp),
        )
        Spacer(Modifier.width(12.dp))
        Text(
            title,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.weight(1f),
        )
        Icon(
            Icons.AutoMirrored.Outlined.KeyboardArrowRight,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.outline,
            modifier = Modifier.size(18.dp),
        )
    }
}
