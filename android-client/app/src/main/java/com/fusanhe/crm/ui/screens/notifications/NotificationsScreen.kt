package com.fusanhe.crm.ui.screens.notifications

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Alarm
import androidx.compose.material.icons.outlined.Campaign
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.RateReview
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.AppNotificationItem
import com.fusanhe.crm.domain.model.NotificationLevel
import com.fusanhe.crm.domain.model.NotificationType
import com.fusanhe.crm.ui.components.EmptyState
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.ListSkeleton
import com.fusanhe.crm.ui.theme.RiskHigh
import com.fusanhe.crm.ui.theme.RiskHighContainer
import com.fusanhe.crm.ui.theme.StatusInfo
import com.fusanhe.crm.ui.theme.StatusInfoContainer
import com.fusanhe.crm.ui.theme.StatusWaiting
import com.fusanhe.crm.ui.theme.StatusWaitingContainer
import com.fusanhe.crm.util.TimeFormat

/**
 * 通知与异常列表：发送异常、超时提醒、审核提醒、系统公告。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationsScreen(
    onBack: () -> Unit,
    onOpenConversation: (String) -> Unit,
    onOpenCustomer: (String) -> Unit,
    viewModel: NotificationsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("通知与异常") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    if (state.unreadCount > 0) {
                        TextButton(onClick = viewModel::markAllRead) { Text("全部已读") }
                    }
                },
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        when {
            state.loading -> ListSkeleton(rows = 8, modifier = Modifier.padding(padding))
            state.items.isEmpty() -> EmptyState(
                icon = Icons.Outlined.Campaign,
                title = "暂无通知",
                description = "发送异常和超时提醒会显示在这里",
                modifier = Modifier.padding(padding),
            )
            else -> LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(state.items, key = { it.id }) { item ->
                    NotificationCard(
                        item = item,
                        onClick = {
                            viewModel.markRead(item.id)
                            when {
                                item.conversationId != null -> onOpenConversation(item.conversationId)
                                item.customerId != null -> onOpenCustomer(item.customerId)
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun NotificationCard(item: AppNotificationItem, onClick: () -> Unit) {
    val (icon, fg, bg) = when (item.level) {
        NotificationLevel.ERROR -> Triple(Icons.Outlined.ErrorOutline, RiskHigh, RiskHighContainer)
        NotificationLevel.WARNING -> Triple(Icons.Outlined.Alarm, StatusWaiting, StatusWaitingContainer)
        NotificationLevel.INFO -> Triple<ImageVector, Color, Color>(Icons.Outlined.RateReview, StatusInfo, StatusInfoContainer)
    }
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (item.read) MaterialTheme.colorScheme.surface
            else MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f),
        ),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(bg),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = item.type.label, tint = fg, modifier = Modifier.size(18.dp))
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        item.title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = if (item.read) FontWeight.Normal else FontWeight.SemiBold,
                        maxLines = 1,
                        modifier = Modifier.weight(1f),
                    )
                    if (!item.read) {
                        Box(
                            Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(MaterialTheme.colorScheme.primary),
                        )
                    }
                }
                Spacer(Modifier.height(2.dp))
                Text(
                    item.content,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    LabelChip(item.type.label, container = bg, content = fg)
                    Text(
                        TimeFormat.formatRelative(item.occurredAt),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
            }
        }
    }
}
