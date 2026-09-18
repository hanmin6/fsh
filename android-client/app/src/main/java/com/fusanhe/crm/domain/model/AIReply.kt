package com.fusanhe.crm.domain.model

enum class RiskLevel(val label: String) {
    LOW("低风险"),
    MEDIUM("中风险"),
    HIGH("高风险"),
}

enum class AIReplyStatus { GENERATING, READY, ACCEPTED, DISMISSED, FAILED }

/**
 * AI 回复建议（对应后端 AIReplyDraft）。
 *
 * confirmReasons 非空时表示内容涉及价格、MOQ、交期、认证、付款、折扣、
 * 质量承诺或赔偿等条款，UI 上必须提示"需要人工确认"。
 */
data class AIReplySuggestion(
    val id: String,
    val conversationId: String,
    val draftText: String,
    val translatedText: String,
    val suggestedLanguage: String,
    val intent: String,
    val summaryZh: String,
    val riskLevel: RiskLevel,
    val confidence: Float,
    val missingInformation: List<String> = emptyList(),
    val citedKnowledge: List<String> = emptyList(),
    val confirmReasons: List<String> = emptyList(),
    val status: AIReplyStatus = AIReplyStatus.READY,
) {
    val needsManualConfirm: Boolean get() = confirmReasons.isNotEmpty()
}
