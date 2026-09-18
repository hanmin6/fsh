package com.fusanhe.crm.ui.screens.chat

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.AttachFile
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material.icons.outlined.ExpandMore
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.TextSnippet
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.MessageDirection
import com.fusanhe.crm.domain.model.MessageDisplayMode
import com.fusanhe.crm.domain.model.OnlineStatus
import com.fusanhe.crm.ui.components.AvatarInitials
import com.fusanhe.crm.ui.components.ChannelIcon
import com.fusanhe.crm.ui.components.DeliveryStatusIcon
import com.fusanhe.crm.ui.components.ErrorState
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.ListSkeleton
import com.fusanhe.crm.ui.theme.RiskHigh
import com.fusanhe.crm.util.TimeFormat

/**
 * 会话详情：商务消息工作台。
 * 顶部客户信息 / 中间消息区（原文+译文切换）/ 底部回复区（翻译、AI 建议、常用语、附件、发送）。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onBack: () -> Unit,
    onCustomerDetail: (String) -> Unit,
    viewModel: ChatViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val clipboard = LocalClipboardManager.current
    val listState = rememberLazyListState()

    fun copyText(text: String) {
        clipboard.setText(AnnotatedString(text))
    }

    LaunchedEffect(Unit) {
        viewModel.events.collect { snackbarHostState.showSnackbar(it) }
    }
    LaunchedEffect(state.messages.size) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(0)
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            ChatTopBar(
                state = state,
                onBack = onBack,
                onCustomerDetail = { state.conversation?.let { onCustomerDetail(it.customerId) } },
                onToggleDisplay = viewModel::toggleDisplayMode,
                onSimulateIncoming = viewModel::simulateIncomingMessage,
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        bottomBar = {
            ChatInputBar(
                state = state,
                onDraftChange = viewModel::onDraftChange,
                onSend = viewModel::sendMessage,
                onOpenTranslate = viewModel::openDraftTranslateSheet,
                onOpenAi = viewModel::openAiSheet,
                onOpenPhrases = viewModel::showPhrasesSheet,
                onAddAttachment = viewModel::addAttachment,
                onRemoveAttachment = viewModel::removeAttachment,
            )
        },
    ) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when {
                state.loading -> ListSkeleton(rows = 6)
                state.error != null && state.conversation == null ->
                    ErrorState(message = state.error!!)
                else -> LazyColumn(
                    state = listState,
                    reverseLayout = true,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    if (state.aiState is AiSuggestionSheetState.Generating) {
                        item(key = "generating") { GeneratingBanner() }
                    }
                    items(state.messages.asReversed(), key = { it.id }) { message ->
                        MessageBubble(
                            message = message,
                            displayMode = state.displayMode,
                            translationOverride = state.messageTranslations[message.id],
                            translating = message.id in state.translatingMessageIds,
                            translateError = state.messageTranslationErrors[message.id],
                            onTranslate = { viewModel.translateMessage(message) },
                            onCopy = ::copyText,
                            onRetrySend = viewModel::sendMessage,
                        )
                    }
                }
            }
        }
    }

    // ---- 弹层 ----
    AiSuggestionSheet(
        visible = state.aiSheetVisible,
        aiState = state.aiState,
        onAdopt = viewModel::adoptSuggestion,
        onEdit = viewModel::openSuggestionEditSheet,
        onRegenerate = { viewModel.generateSuggestion(regenerate = true) },
        onClose = viewModel::closeAiSheet,
    )
    TranslateEditSheet(
        sheetState = state.translateSheet,
        onOriginalChange = viewModel::onSheetOriginalChange,
        onTranslatedChange = viewModel::onSheetTranslatedChange,
        onSwap = viewModel::swapSheetDisplay,
        onAdopt = viewModel::adoptSheetText,
        onRetry = viewModel::retrySheetTranslation,
        onClose = viewModel::closeTranslateSheet,
    )
    QuickPhrasesSheet(
        visible = state.phrasesSheetVisible,
        phrases = MockData.quickPhrases,
        onUse = viewModel::usePhrase,
        onDismiss = viewModel::hidePhrasesSheet,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChatTopBar(
    state: ChatUiState,
    onBack: () -> Unit,
    onCustomerDetail: () -> Unit,
    onToggleDisplay: () -> Unit,
    onSimulateIncoming: () -> Unit,
) {
    val conversation = state.conversation
    var menuOpen by remember { mutableStateOf(false) }
    Column {
        TopAppBar(
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "返回")
                }
            },
            title = {
                if (conversation != null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AvatarInitials(conversation.customerName, size = 34.dp)
                        Spacer(Modifier.width(8.dp))
                        Column {
                            Text(
                                conversation.customerName,
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                "${conversation.companyName} · ${conversation.country}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                            )
                        }
                    }
                } else {
                    Text("会话")
                }
            },
                actions = {
                    if (conversation != null) {
                        IconButton(onClick = onCustomerDetail) {
                            Icon(
                                Icons.Outlined.Person,
                                contentDescription = "查看客户详情",
                            )
                        }
                    }
                IconButton(onClick = { menuOpen = true }) {
                    Icon(Icons.Outlined.ExpandMore, contentDescription = "更多")
                }
                DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                    DropdownMenuItem(
                        text = { Text("模拟客户消息") },
                        onClick = {
                            menuOpen = false
                            onSimulateIncoming()
                        },
                    )
                    DropdownMenuItem(
                        text = { Text("查看客户详情") },
                        onClick = {
                            menuOpen = false
                            onCustomerDetail()
                        },
                    )
                    DropdownMenuItem(
                        text = {
                            Text(
                                if (state.displayMode == MessageDisplayMode.ORIGINAL_ONLY) "显示原文+译文" else "仅显示原文"
                            )
                        },
                        onClick = {
                            menuOpen = false
                            onToggleDisplay()
                        },
                    )
                }
            },
        )
        if (conversation != null) {
            Surface(color = MaterialTheme.colorScheme.surface) {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    LabelChip(conversation.channel.label)
                    LabelChip(conversation.subject, container = MaterialTheme.colorScheme.surfaceVariant)
                    OnlineStatusChip(conversation.onlineStatus)
                    if (conversation.slaBreached) {
                        LabelChip("已超时", container = RiskHigh.copy(alpha = 0.12f), content = RiskHigh)
                    }
                    Spacer(Modifier.weight(1f))
                    // 原文/译文切换
                    TextButton(
                        onClick = onToggleDisplay,
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 8.dp),
                    ) {
                        Icon(Icons.Outlined.Translate, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text(
                            if (state.displayMode == MessageDisplayMode.ORIGINAL_ONLY) "仅原文" else "原文+译文",
                            style = MaterialTheme.typography.labelMedium,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun OnlineStatusChip(status: OnlineStatus) {
    when (status) {
        OnlineStatus.ONLINE -> LabelChip(
            "在线",
            container = com.fusanhe.crm.ui.theme.StatusSuccessContainer,
            content = com.fusanhe.crm.ui.theme.StatusSuccess,
        )
        OnlineStatus.RECENT_ACTIVE -> LabelChip("最近活跃")
        OnlineStatus.OFFLINE -> LabelChip("离线")
    }
}

@Composable
private fun GeneratingBanner() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(modifier = Modifier.size(14.dp), strokeWidth = 2.dp)
        Spacer(Modifier.width(8.dp))
        Text(
            "AI 正在生成回复…",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun MessageBubble(
    message: Message,
    displayMode: MessageDisplayMode,
    translationOverride: String?,
    translating: Boolean,
    translateError: String?,
    onTranslate: () -> Unit,
    onCopy: (String) -> Unit,
    onRetrySend: () -> Unit,
) {
    val incoming = message.direction == MessageDirection.INCOMING
    val translationText = translationOverride ?: message.translatedText

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (incoming) Alignment.Start else Alignment.End,
    ) {
        Text(
            "${message.senderName} · ${TimeFormat.formatDateTime(message.sentAt)}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.outline,
        )
        Spacer(Modifier.height(4.dp))
        Surface(
            color = if (incoming) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.primaryContainer,
            shape = RoundedCornerShape(
                topStart = if (incoming) 4.dp else 12.dp,
                topEnd = if (incoming) 12.dp else 4.dp,
                bottomStart = 12.dp,
                bottomEnd = 12.dp,
            ),
            modifier = Modifier
                .widthIn(max = 300.dp)
                .combinedClickable(onClick = {}, onLongClick = { onCopy(message.originalText) }),
        ) {
            Column(Modifier.padding(12.dp)) {
                SelectionContainer {
                    Text(
                        message.originalText,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (incoming) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
                // 附件占位
                message.attachments.forEach { attachment ->
                    Spacer(Modifier.height(6.dp))
                    LabelChip("${attachment.name}（${attachment.sizeLabel}）")
                }
                // 译文
                val showTranslation = displayMode == MessageDisplayMode.ORIGINAL_WITH_TRANSLATION
                if (incoming && showTranslation && translationText != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "中文翻译",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (incoming) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                    Text(
                        translationText,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (incoming) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
                if (!incoming && showTranslation && translationText != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "已翻译为${languageLabel(message.language)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                    Text(
                        translationText,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
            }
        }
        Spacer(Modifier.height(4.dp))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (message.aiAssisted) {
                LabelChip("AI 辅助")
            }
            if (!incoming) {
                DeliveryStatusIcon(message.deliveryStatus)
                Text(
                    message.deliveryStatus.label,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (message.deliveryStatus == com.fusanhe.crm.domain.model.DeliveryStatus.FAILED) {
                        RiskHigh
                    } else {
                        MaterialTheme.colorScheme.outline
                    },
                )
                if (message.deliveryStatus == com.fusanhe.crm.domain.model.DeliveryStatus.FAILED) {
                    TextButton(onClick = onRetrySend, contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 6.dp)) {
                        Text("重试", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
            if (incoming && translationText == null) {
                when {
                    translating -> CircularProgressIndicator(modifier = Modifier.size(12.dp), strokeWidth = 2.dp)
                    translateError != null -> {
                        Text(
                            "翻译失败",
                            style = MaterialTheme.typography.labelSmall,
                            color = RiskHigh,
                        )
                        TextButton(
                            onClick = onTranslate,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 6.dp),
                        ) { Text("重试", style = MaterialTheme.typography.labelMedium) }
                    }
                    else -> TextButton(
                        onClick = onTranslate,
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 6.dp),
                    ) {
                        Icon(Icons.Outlined.Translate, contentDescription = null, modifier = Modifier.size(14.dp))
                        Spacer(Modifier.width(2.dp))
                        Text("翻译", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        }
    }
}

private fun languageLabel(code: String): String = when (code) {
    "en" -> "英语"
    "es" -> "西班牙语"
    "fr" -> "法语"
    "ja" -> "日语"
    "zh" -> "中文"
    else -> "客户语言"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChatInputBar(
    state: ChatUiState,
    onDraftChange: (String) -> Unit,
    onSend: () -> Unit,
    onOpenTranslate: () -> Unit,
    onOpenAi: () -> Unit,
    onOpenPhrases: () -> Unit,
    onAddAttachment: (Attachment) -> Unit,
    onRemoveAttachment: (String) -> Unit,
) {
    var attachMenuOpen by remember { mutableStateOf(false) }
    Surface(color = MaterialTheme.colorScheme.surface, shadowElevation = 8.dp) {
        Column(
            Modifier
                .fillMaxWidth()
                .imePadding()
                .padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            if (state.attachments.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    state.attachments.forEach { attachment ->
                        Box(
                            Modifier.clickable { onRemoveAttachment(attachment.id) },
                        ) {
                            LabelChip("${attachment.name} ✕", content = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
                Spacer(Modifier.height(6.dp))
            }
            OutlinedTextField(
                value = state.draft,
                onValueChange = onDraftChange,
                placeholder = { Text("输入回复内容（演示模式，不会真实发送）", maxLines = 1) },
                maxLines = 4,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onOpenTranslate) {
                    Icon(Icons.Outlined.Translate, contentDescription = "翻译草稿")
                }
                IconButton(onClick = onOpenAi) {
                    Icon(Icons.Outlined.AutoAwesome, contentDescription = "AI 回复建议")
                }
                IconButton(onClick = onOpenPhrases) {
                    Icon(Icons.Outlined.TextSnippet, contentDescription = "常用语")
                }
                Box {
                    IconButton(onClick = { attachMenuOpen = true }) {
                        Icon(Icons.Outlined.AttachFile, contentDescription = "附件")
                    }
                    DropdownMenu(
                        expanded = attachMenuOpen,
                        onDismissRequest = { attachMenuOpen = false },
                    ) {
                        MockData.attachmentPresets.forEach { attachment ->
                            DropdownMenuItem(
                                text = { Text("${attachment.name}（${attachment.sizeLabel}）") },
                                onClick = {
                                    attachMenuOpen = false
                                    onAddAttachment(attachment)
                                },
                            )
                        }
                    }
                }
                Spacer(Modifier.weight(1f))
                Button(onClick = onSend, enabled = state.draft.isNotBlank() && !state.sending) {
                    if (state.sending) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    } else {
                        Icon(Icons.AutoMirrored.Outlined.Send, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("发送")
                    }
                }
            }
        }
    }
}
