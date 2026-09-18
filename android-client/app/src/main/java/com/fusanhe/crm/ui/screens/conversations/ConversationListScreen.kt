package com.fusanhe.crm.ui.screens.conversations

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Forum
import androidx.compose.material3.Badge
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.ui.components.AvatarInitials
import com.fusanhe.crm.ui.components.ChannelIcon
import com.fusanhe.crm.ui.components.EmptyState
import com.fusanhe.crm.ui.components.ErrorState
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.ListSkeleton
import com.fusanhe.crm.ui.components.OfflineBanner
import com.fusanhe.crm.ui.theme.FusanheTheme
import com.fusanhe.crm.ui.theme.RiskHigh
import com.fusanhe.crm.ui.theme.RiskHighContainer
import com.fusanhe.crm.ui.theme.StatusWaiting
import com.fusanhe.crm.ui.theme.StatusWaitingContainer
import com.fusanhe.crm.util.TimeFormat

/**
 * 询盘列表：状态筛选、下拉刷新、超时标记、未读徽标。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationListScreen(
    onConversationClick: (String) -> Unit,
    viewModel: ConversationListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize()) {
        Text(
            "询盘",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
        )
        Row(
            Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            ConversationFilter.entries.forEach { filter ->
                FilterChip(
                    selected = state.filter == filter,
                    onClick = { viewModel.setFilter(filter) },
                    label = { Text(filter.label) },
                )
            }
        }
        Spacer(Modifier.height(4.dp))
        if (state.offline) {
            OfflineBanner("当前处于离线演示模式")
        }

        PullToRefreshBox(
            isRefreshing = state.refreshing,
            onRefresh = viewModel::refresh,
            modifier = Modifier.fillMaxSize(),
        ) {
            when {
                state.initialLoading -> ListSkeleton(rows = 7)
                state.error != null && state.conversations.isEmpty() ->
                    ErrorState(message = state.error!!, onRetry = viewModel::refresh)
                state.conversations.isEmpty() -> EmptyState(
                    icon = Icons.Outlined.Forum,
                    title = "暂无询盘",
                    description = when (state.filter) {
                        ConversationFilter.ALL -> "客户发来询盘后会显示在这里"
                        else -> "当前筛选条件下没有询盘"
                    },
                )
                else -> LazyColumn(
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.conversations, key = { it.id }) { conversation ->
                        ConversationCard(conversation, onConversationClick)
                    }
                }
            }
        }
    }
}

@Composable
private fun ConversationCard(conversation: Conversation, onClick: (String) -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick(conversation.id) },
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AvatarInitials(conversation.customerName, size = 38.dp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        conversation.customerName,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        conversation.companyName,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                ChannelIcon(conversation.channel, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(8.dp))
                Text(
                    TimeFormat.formatRelative(conversation.lastMessageAt),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.outline,
                )
                if (conversation.unreadCount > 0) {
                    Spacer(Modifier.width(6.dp))
                    Badge { Text("${conversation.unreadCount}") }
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                conversation.subject,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(2.dp))
            Text(
                conversation.lastMessagePreview,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(8.dp))
            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                conversation.product?.let { LabelChip(it) }
                LabelChip(conversation.status.label)
                if (conversation.slaBreached) {
                    LabelChip("已超时 ${TimeFormat.formatWaitingMinutes(conversation.waitingMinutes)}", container = RiskHighContainer, content = RiskHigh)
                } else if (conversation.waitingMinutes > 0) {
                    LabelChip("等待 ${TimeFormat.formatWaitingMinutes(conversation.waitingMinutes)}", container = StatusWaitingContainer, content = StatusWaiting)
                }
                if (conversation.onlineStatus == com.fusanhe.crm.domain.model.OnlineStatus.ONLINE) {
                    Box(
                        Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.primary),
                    )
                    Text(
                        "在线",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }
}
