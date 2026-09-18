package com.fusanhe.crm.ui.screens.customerdetail

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.Chat
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.Email
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Mail
import androidx.compose.material.icons.outlined.Notes
import androidx.compose.material.icons.outlined.Send
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.HistoryType
import com.fusanhe.crm.ui.components.AvatarInitials
import com.fusanhe.crm.ui.components.ErrorState
import com.fusanhe.crm.ui.components.InfoRow
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.ListSkeleton
import com.fusanhe.crm.ui.components.SectionTitle
import com.fusanhe.crm.ui.components.StatTile
import com.fusanhe.crm.ui.theme.FusanheTheme
import com.fusanhe.crm.ui.theme.RiskHigh
import com.fusanhe.crm.ui.theme.StatusInfo
import com.fusanhe.crm.ui.theme.StatusWaiting
import com.fusanhe.crm.util.TimeFormat
import kotlinx.coroutines.launch

/**
 * 客户详情：客户概要 + 跟进概览 + 历史时间线。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CustomerDetailScreen(
    onBack: () -> Unit,
    onOpenConversation: (String) -> Unit,
    viewModel: CustomerDetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    val s = state as? CustomerDetailUiState.Content
                    Text(s?.customer?.name ?: "客户详情")
                },
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
        when (val s = state) {
            CustomerDetailUiState.Loading -> ListSkeleton(rows = 7, modifier = Modifier.padding(padding))
            is CustomerDetailUiState.Error -> ErrorState(
                message = s.message,
                onRetry = viewModel::load,
                modifier = Modifier.padding(padding),
            )
            is CustomerDetailUiState.Content -> CustomerDetailContent(
                content = s,
                snackbarHostState = snackbarHostState,
                onOpenConversation = onOpenConversation,
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun CustomerDetailContent(
    content: CustomerDetailUiState.Content,
    snackbarHostState: SnackbarHostState,
    onOpenConversation: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val customer = content.customer
    val scope = rememberCoroutineScope()

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(bottom = 24.dp),
    ) {
        // ---- 客户概要 ----
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
        ) {
            Column(Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    AvatarInitials(customer.name, size = 52.dp)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            customer.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            customer.companyName,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(4.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            LabelChip(customer.country)
                            LabelChip(customer.source.label)
                            LabelChip(customer.level.label.split(" ").first())
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                Spacer(Modifier.height(8.dp))
                InfoRow("邮箱", customer.email ?: "—")
                InfoRow("电话", customer.phone ?: "—")
                InfoRow("WhatsApp", customer.whatsapp ?: "—")
                customer.alibabaId?.let { InfoRow("阿里账号", it) }
                customer.madeInChinaId?.let { InfoRow("MIC 账号", it) }
                customer.jobTitle?.let { InfoRow("职位", it) }
                InfoRow("负责人", customer.ownerName)
                InfoRow("最近联系", customer.lastContactAt?.let { TimeFormat.formatRelative(it) } ?: "—")
                if (customer.tags.isNotEmpty()) {
                    InfoRow("标签", customer.tags.joinToString("、"))
                }
                if (!customer.notes.isNullOrBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        customer.notes!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = { scope.launch { snackbarHostState.showSnackbar("演示模式：已打开邮件编辑（未真实发送）") } },
                        modifier = Modifier.weight(1f),
                    ) { Text("邮件", maxLines = 1) }
                    OutlinedButton(
                        onClick = { scope.launch { snackbarHostState.showSnackbar("演示模式：拨打电话（未真实拨打）") } },
                        modifier = Modifier.weight(1f),
                    ) { Text("电话", maxLines = 1) }
                    OutlinedButton(
                        onClick = { scope.launch { snackbarHostState.showSnackbar("演示模式：打开 WhatsApp（未真实发送）") } },
                        modifier = Modifier.weight(1.35f),
                    ) { Text("WhatsApp", maxLines = 1) }
                }
            }
        }

        // ---- 跟进概览 ----
        SectionTitle("跟进概览", modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
        Row(
            modifier = Modifier.padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatTile(
                label = "询盘数量",
                value = "${content.followUp.inquiryCount}",
                valueColor = MaterialTheme.colorScheme.primary,
                modifier = Modifier.weight(1f),
            )
            StatTile(
                label = "待回复",
                value = "${content.followUp.waitingCount}",
                valueColor = StatusWaiting,
                modifier = Modifier.weight(1f),
            )
        }
        Spacer(Modifier.height(10.dp))
        Row(
            modifier = Modifier.padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            StatTile(
                label = "最近回复",
                value = content.followUp.lastReplyAt?.let { TimeFormat.formatRelative(it) } ?: "—",
                valueColor = StatusInfo,
                modifier = Modifier.weight(1f),
            )
            StatTile(
                label = "跟进状态",
                value = content.followUp.followStatus,
                valueColor = MaterialTheme.colorScheme.onSurface,
                modifier = Modifier.weight(1f),
            )
        }
        if (customer.interestedProducts.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
            ) {
                Column(Modifier.padding(12.dp)) {
                    Text(
                        "感兴趣的产品",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        customer.interestedProducts.forEach { LabelChip(it) }
                    }
                }
            }
        }

        // ---- 历史时间线 ----
        SectionTitle("历史时间线", modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
        if (content.history.isEmpty()) {
            Text(
                "暂无历史记录",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        } else {
            Column(
                modifier = Modifier.padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                content.history.forEach { item ->
                    HistoryCard(item, onOpenConversation)
                }
            }
        }
    }
}

@Composable
private fun HistoryCard(item: CustomerHistoryItem, onOpenConversation: (String) -> Unit) {
    val (icon, tint) = historyIcon(item.type)
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier
            .fillMaxWidth()
            .then(
                if (item.conversationId != null) {
                    Modifier.clickable { onOpenConversation(item.conversationId) }
                } else {
                    Modifier
                }
            ),
    ) {
        Row(Modifier.padding(12.dp)) {
            Box(
                modifier = Modifier
                    .size(34.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = item.type.label, tint = tint, modifier = Modifier.size(17.dp))
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        item.title,
                        style = MaterialTheme.typography.titleSmall,
                        maxLines = 1,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        TimeFormat.formatRelative(item.occurredAt),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
                Spacer(Modifier.height(3.dp))
                Text(
                    item.content,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(6.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    LabelChip(item.type.label)
                    item.channel?.let { LabelChip(it.label) }
                    LabelChip(item.status.label)
                    LabelChip(item.actorName)
                    if (item.aiAssisted) {
                        LabelChip(
                            "AI 辅助",
                            container = StatusInfo.copy(alpha = 0.12f),
                            content = StatusInfo,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun historyIcon(type: HistoryType): Pair<ImageVector, Color> = when (type) {
    HistoryType.INQUIRY -> Icons.Outlined.Mail to MaterialTheme.colorScheme.primary
    HistoryType.REPLY -> Icons.Outlined.Send to MaterialTheme.colorScheme.primary
    HistoryType.AI_DRAFT -> Icons.Outlined.AutoAwesome to StatusInfo
    HistoryType.CALL -> Icons.Outlined.Call to StatusInfo
    HistoryType.EMAIL -> Icons.Outlined.Email to StatusInfo
    HistoryType.WHATSAPP -> Icons.Outlined.Chat to MaterialTheme.colorScheme.primary
    HistoryType.PROFILE_UPDATE -> Icons.Outlined.Edit to StatusWaiting
    HistoryType.FOLLOW_UP_NOTE -> Icons.Outlined.Notes to StatusWaiting
    HistoryType.SEND_FAILURE -> Icons.Outlined.ErrorOutline to RiskHigh
}
