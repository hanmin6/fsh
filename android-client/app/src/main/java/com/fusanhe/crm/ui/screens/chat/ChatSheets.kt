package com.fusanhe.crm.ui.screens.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.SwapVert
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.fusanhe.crm.domain.model.QuickPhrase
import com.fusanhe.crm.ui.components.InfoRow
import com.fusanhe.crm.ui.components.LabelChip
import com.fusanhe.crm.ui.components.RiskBadge
import com.fusanhe.crm.ui.theme.RiskHigh
import com.fusanhe.crm.ui.theme.RiskHighContainer
import com.fusanhe.crm.ui.theme.StatusWaiting
import com.fusanhe.crm.util.TimeFormat

/**
 * AI 回复建议弹层：建议内容、风险等级、置信度、缺失信息、引用知识、采用/编辑/重新生成/复制。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AiSuggestionSheet(
    visible: Boolean,
    aiState: AiSuggestionSheetState,
    onAdopt: () -> Unit,
    onEdit: (com.fusanhe.crm.domain.model.AIReplySuggestion) -> Unit,
    onRegenerate: () -> Unit,
    onClose: () -> Unit,
) {
    if (!visible) return
    ModalBottomSheet(onDismissRequest = onClose) {
        when (aiState) {
            AiSuggestionSheetState.Hidden -> Unit
            AiSuggestionSheetState.Generating -> Column(
                modifier = Modifier.fillMaxWidth().padding(32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator()
                Spacer(Modifier.height(12.dp))
                Text("AI 正在生成回复…", style = MaterialTheme.typography.bodyMedium)
                Text(
                    "正在结合客户信息与知识库内容",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            is AiSuggestionSheetState.Failed -> Column(
                modifier = Modifier.fillMaxWidth().padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = RiskHigh)
                Spacer(Modifier.height(8.dp))
                Text("生成失败", style = MaterialTheme.typography.titleMedium)
                Text(
                    aiState.message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onRegenerate) { Text("重新生成") }
                    TextButton(onClick = onClose) { Text("关闭") }
                }
            }
            is AiSuggestionSheetState.Ready -> ReadyContent(
                state = aiState,
                onAdopt = onAdopt,
                onEdit = onEdit,
                onRegenerate = onRegenerate,
                onClose = onClose,
            )
        }
        Spacer(Modifier.height(16.dp))
    }
}

@Composable
private fun ReadyContent(
    state: AiSuggestionSheetState.Ready,
    onAdopt: () -> Unit,
    onEdit: (com.fusanhe.crm.domain.model.AIReplySuggestion) -> Unit,
    onRegenerate: () -> Unit,
    onClose: () -> Unit,
) {
    val suggestion = state.suggestion
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Outlined.AutoAwesome,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(6.dp))
            Text(
                "AI 回复建议",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            RiskBadge(suggestion.riskLevel)
        }
        Spacer(Modifier.height(10.dp))

        if (suggestion.needsManualConfirm) {
            Card(colors = CardDefaults.cardColors(containerColor = RiskHighContainer)) {
                Column(Modifier.padding(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Outlined.ErrorOutline,
                            contentDescription = null,
                            tint = RiskHigh,
                            modifier = Modifier.size(16.dp),
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            "需要人工确认",
                            style = MaterialTheme.typography.titleSmall,
                            color = RiskHigh,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    Spacer(Modifier.height(4.dp))
                    Text(
                        suggestion.confirmReasons.joinToString("；"),
                        style = MaterialTheme.typography.bodySmall,
                        color = RiskHigh,
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
        }

        // 建议草稿（客户语言）
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
            Column(Modifier.padding(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LabelChip("建议语言：${suggestion.suggestedLanguage}")
                    Spacer(Modifier.weight(1f))
                    Text(
                        "置信度 ${TimeFormat.formatConfidence(suggestion.confidence)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(Modifier.height(8.dp))
                SelectionContainer {
                    Text(suggestion.draftText, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        Spacer(Modifier.height(8.dp))

        // 中文译文
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(Modifier.padding(12.dp)) {
                Text(
                    "中文译文",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                Text(suggestion.translatedText, style = MaterialTheme.typography.bodyMedium)
            }
        }
        Spacer(Modifier.height(8.dp))

        InfoRow("客户意图", suggestion.intent)
        InfoRow("内容摘要", suggestion.summaryZh)

        if (suggestion.missingInformation.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Text(
                "缺失信息",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            suggestion.missingInformation.forEach {
                Text("· $it", style = MaterialTheme.typography.bodySmall)
            }
        }

        if (suggestion.citedKnowledge.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Text(
                "引用知识资料",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                suggestion.citedKnowledge.forEach { LabelChip(it) }
            }
        }

        Spacer(Modifier.height(14.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Button(onClick = onAdopt, modifier = Modifier.weight(1f)) { Text("采用") }
            FilledTonalButton(onClick = { onEdit(suggestion) }, modifier = Modifier.weight(1f)) {
                Text("编辑后采用")
            }
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            TextButton(onClick = onRegenerate) {
                Icon(Icons.Outlined.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(4.dp))
                Text("重新生成")
            }
            TextButton(onClick = onClose) { Text("关闭") }
        }
    }
}

/**
 * 翻译编辑弹层：
 * - 翻译业务员草稿（中文 → 客户语言）
 * - 编辑 AI 建议（客户语言草稿 + 中文对照）
 * 支持交换原文/译文展示、失败重试、查看原文。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TranslateEditSheet(
    sheetState: TranslateSheetState,
    onOriginalChange: (String) -> Unit,
    onTranslatedChange: (String) -> Unit,
    onSwap: () -> Unit,
    onAdopt: () -> Unit,
    onRetry: () -> Unit,
    onClose: () -> Unit,
) {
    when (sheetState) {
        TranslateSheetState.Hidden -> Unit
        is TranslateSheetState.Loading -> ModalBottomSheet(onDismissRequest = onClose) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(32.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator()
                Spacer(Modifier.height(12.dp))
                Text("翻译中…", style = MaterialTheme.typography.bodyMedium)
                Text(
                    sheetState.sourceText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "机器翻译，请人工确认",
                    style = MaterialTheme.typography.labelSmall,
                    color = StatusWaiting,
                )
            }
        }
        is TranslateSheetState.Result -> ModalBottomSheet(onDismissRequest = onClose) {
            val editingReply = sheetState.translatingReply
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(horizontal = 16.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        if (editingReply) "翻译回复（${sheetState.sourceLanguage.label} → ${sheetState.targetLanguage.label}）"
                        else "编辑 AI 建议（${sheetState.targetLanguage.label} 对照）",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(onClick = onSwap) {
                        Icon(Icons.Outlined.SwapVert, contentDescription = "交换原文与译文展示")
                    }
                }
                Spacer(Modifier.height(6.dp))

                val firstText = if (sheetState.swapped) sheetState.translatedText else sheetState.originalText
                val secondText = if (sheetState.swapped) sheetState.originalText else sheetState.translatedText
                val firstLabel = if (sheetState.swapped) "译文" else "原文"
                val secondLabel = if (sheetState.swapped) "原文" else "译文"

                OutlinedTextField(
                    value = firstText,
                    onValueChange = { if (sheetState.swapped) onTranslatedChange(it) else onOriginalChange(it) },
                    label = { Text(firstLabel) },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = secondText,
                    onValueChange = { if (sheetState.swapped) onOriginalChange(it) else onTranslatedChange(it) },
                    label = { Text(secondLabel) },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(8.dp))
                Text(
                    "机器翻译，请人工确认",
                    style = MaterialTheme.typography.labelSmall,
                    color = StatusWaiting,
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = onAdopt, modifier = Modifier.weight(1f)) {
                        Text(if (editingReply) "采用译文填入输入框" else "采用草稿填入输入框")
                    }
                    TextButton(onClick = onClose) { Text("关闭") }
                }
                Spacer(Modifier.height(16.dp))
            }
        }
        is TranslateSheetState.Failed -> ModalBottomSheet(onDismissRequest = onClose) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Icon(Icons.Outlined.ErrorOutline, contentDescription = null, tint = RiskHigh)
                Spacer(Modifier.height(8.dp))
                Text("翻译失败", style = MaterialTheme.typography.titleMedium)
                Text(
                    sheetState.message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(10.dp))
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            "原文",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(sheetState.sourceText, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onRetry) { Text("重试翻译") }
                    TextButton(onClick = onClose) { Text("关闭") }
                }
            }
        }
    }
}

/** 常用语选择弹层 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuickPhrasesSheet(
    visible: Boolean,
    phrases: List<QuickPhrase>,
    onUse: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    if (!visible) return
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.padding(horizontal = 16.dp)) {
            Text(
                "常用语",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                "点击后将插入输入框，可在发送前编辑或翻译",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            phrases.forEach { phrase ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    LabelChip(phrase.category)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        phrase.text,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(onClick = { onUse(phrase.text) }) { Text("插入") }
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
