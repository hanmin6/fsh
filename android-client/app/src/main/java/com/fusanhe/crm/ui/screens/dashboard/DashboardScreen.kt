package com.fusanhe.crm.ui.screens.dashboard

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Alarm
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Inbox
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.ui.components.AvatarInitials
import com.fusanhe.crm.ui.components.EmptyState
import com.fusanhe.crm.ui.components.ErrorState
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.ListSkeleton
import com.fusanhe.crm.ui.components.OfflineBanner
import com.fusanhe.crm.ui.components.SectionTitle
import com.fusanhe.crm.ui.components.StatTile
import com.fusanhe.crm.ui.theme.FusanheTheme
import com.fusanhe.crm.ui.theme.RiskHigh
import com.fusanhe.crm.ui.theme.RiskHighContainer
import com.fusanhe.crm.ui.theme.RiskMedium
import com.fusanhe.crm.ui.theme.StatusInfo
import com.fusanhe.crm.ui.theme.StatusWaiting
import com.fusanhe.crm.util.TimeFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 工作台首页：今日概览指标、发送异常、快速操作、最近客户与最近询盘。
 */
@Composable
fun DashboardScreen(
    onAddCustomer: () -> Unit,
    onCustomerClick: (String) -> Unit,
    onConversationClick: (String) -> Unit,
    onConversationsTab: () -> Unit,
    onNotifications: () -> Unit,
    viewModel: DashboardViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize()) {
        Text(
            "工作台",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
        )
        when (val s = state) {
            DashboardUiState.Loading -> ListSkeleton(rows = 6)
            is DashboardUiState.Error -> ErrorState(message = s.message, onRetry = viewModel::refresh)
            is DashboardUiState.Content -> DashboardContent(
                state = s,
                viewModel = viewModel,
                onAddCustomer = onAddCustomer,
                onCustomerClick = onCustomerClick,
                onConversationClick = onConversationClick,
                onConversationsTab = onConversationsTab,
                onNotifications = onNotifications,
            )
        }
    }
}

@Composable
private fun DashboardContent(
    state: DashboardUiState.Content,
    viewModel: DashboardViewModel,
    onAddCustomer: () -> Unit,
    onCustomerClick: (String) -> Unit,
    onConversationClick: (String) -> Unit,
    onConversationsTab: () -> Unit,
    onNotifications: () -> Unit,
) {
    val data = state.data
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
    ) {
        item {
            if (state.offline) {
                OfflineBanner("当前处于离线演示模式，展示的是缓存数据")
            }
            GreetingCard(
                userName = viewModel.currentUser.name,
                sendFailures = data.sendFailures,
                onNotifications = onNotifications,
            )
        }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                StatTile(
                    label = "今日新增询盘",
                    value = "${data.todayNewInquiries}",
                    valueColor = MaterialTheme.colorScheme.primary,
                    icon = Icons.Outlined.Inbox,
                    onClick = onConversationsTab,
                    modifier = Modifier.weight(1f),
                )
                StatTile(
                    label = "待回复",
                    value = "${data.pendingReplies}",
                    valueColor = StatusWaiting,
                    icon = Icons.Outlined.Schedule,
                    onClick = onConversationsTab,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .padding(top = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                StatTile(
                    label = "待审核回复",
                    value = "${data.pendingReviews}",
                    valueColor = StatusInfo,
                    icon = Icons.Outlined.Alarm,
                    onClick = onConversationsTab,
                    modifier = Modifier.weight(1f),
                )
                StatTile(
                    label = "超时询盘",
                    value = "${data.overdueInquiries}",
                    valueColor = RiskHigh,
                    icon = Icons.Outlined.ErrorOutline,
                    onClick = onConversationsTab,
                    modifier = Modifier.weight(1f),
                )
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                FilledTonalButton(onClick = onAddCustomer, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Outlined.Add, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text("新增客户")
                }
                FilledTonalButton(onClick = onNotifications, modifier = Modifier.weight(1f)) {
                    Text("通知与异常")
                }
            }
        }

        item {
            SectionTitle(
                "最近客户",
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            ) {
                Column {
                    data.recentCustomers.forEachIndexed { index, customer ->
                        DashboardCustomerRow(customer, onCustomerClick)
                        if (index < data.recentCustomers.lastIndex) {
                            androidx.compose.material3.HorizontalDivider(
                                color = MaterialTheme.colorScheme.surfaceVariant,
                            )
                        }
                    }
                }
            }
        }

        item {
            SectionTitle(
                "最近询盘",
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            ) {
                Column {
                    data.recentConversations.forEachIndexed { index, conversation ->
                        DashboardConversationRow(conversation, onConversationClick)
                        if (index < data.recentConversations.lastIndex) {
                            androidx.compose.material3.HorizontalDivider(
                                color = MaterialTheme.colorScheme.surfaceVariant,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun GreetingCard(
    userName: String,
    sendFailures: Int,
    onNotifications: () -> Unit,
) {
    val dateText = SimpleDateFormat("M月d日 EEEE", Locale.CHINA).format(Date())
    Column(Modifier.padding(16.dp)) {
        Text(
            "你好，$userName",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(2.dp))
        Text(
            "今天是 $dateText，祝你顺利",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (sendFailures > 0) {
            Spacer(Modifier.height(10.dp))
            Card(
                colors = CardDefaults.cardColors(containerColor = RiskHighContainer),
                modifier = Modifier.fillMaxWidth().clickable(onClick = onNotifications),
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Outlined.ErrorOutline,
                        contentDescription = null,
                        tint = RiskHigh,
                        modifier = Modifier.size(18.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "$sendFailures 条消息发送失败，点击查看",
                        style = MaterialTheme.typography.bodyMedium,
                        color = RiskHigh,
                    )
                }
            }
        }
    }
}

@Composable
private fun DashboardCustomerRow(customer: Customer, onClick: (String) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick(customer.id) }
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AvatarInitials(customer.name, size = 36.dp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(customer.name, style = MaterialTheme.typography.bodyLarge, maxLines = 1)
            Text(
                customer.companyName,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
        }
        Text(
            customer.lastContactAt?.let { TimeFormat.formatRelative(it) } ?: "未联系",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}

@Composable
private fun DashboardConversationRow(conversation: Conversation, onClick: (String) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick(conversation.id) }
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AvatarInitials(conversation.customerName, size = 36.dp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(
                "${conversation.customerName} · ${conversation.subject}",
                style = MaterialTheme.typography.bodyLarge,
                maxLines = 1,
            )
            Text(
                conversation.lastMessagePreview,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                TimeFormat.formatRelative(conversation.lastMessageAt),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.outline,
            )
            Spacer(Modifier.height(4.dp))
            if (conversation.slaBreached) {
                LabelChip("超时", container = RiskHighContainer, content = RiskHigh)
            } else {
                LabelChip(conversation.status.label)
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun DashboardPreview() {
    FusanheTheme {
        TextButton(onClick = {}) { Text("Dashboard preview — run app for full UI") }
    }
}
