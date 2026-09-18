package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.AIReplyStatus
import com.fusanhe.crm.domain.model.AIReplySuggestion
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.RiskLevel
import com.fusanhe.crm.domain.repository.AIReplyRepository
import com.fusanhe.crm.domain.repository.ConversationRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * AI 回复建议仓库 Mock 实现：
 * 演示会话命中预置建议，其他会话按会话内容即时生成通用建议。
 */
@Singleton
class MockAIReplyRepository @Inject constructor(
    private val conversationRepository: ConversationRepository,
    private val mode: MockModeController,
) : AIReplyRepository {

    private val _latest = MutableStateFlow(
        MockData.suggestions.associateBy { it.conversationId }
    )

    private var regenerateCount = 0

    override fun observeLatestSuggestion(conversationId: String): Flow<AIReplySuggestion?> =
        _latest.asStateFlow().map { it[conversationId] }

    override suspend fun generateSuggestion(conversationId: String): Result<AIReplySuggestion> {
        delay(600)
        if (mode.flags.value.offline) {
            return Result.failure(java.io.IOException("网络连接失败（演示模式）"))
        }
        // 模拟 AI 生成耗时
        delay(1400)
        val base = _latest.value[conversationId]
            ?: MockData.suggestions.firstOrNull { it.conversationId == conversationId }
            ?: buildGenericSuggestion(conversationId, variant = 0)
        val suggestion = base.copy(
            id = "sug_${UUID.randomUUID().toString().take(8)}",
            status = AIReplyStatus.READY,
        )
        _latest.update { it + (conversationId to suggestion) }
        return Result.success(suggestion)
    }

    override suspend fun regenerateSuggestion(conversationId: String): Result<AIReplySuggestion> {
        delay(400)
        if (mode.flags.value.offline) {
            return Result.failure(java.io.IOException("网络连接失败（演示模式）"))
        }
        delay(1200)
        val variant = ++regenerateCount
        val conversation = conversationRepository.getConversation(conversationId).getOrNull()
        val base = _latest.value[conversationId]
            ?: buildGenericSuggestion(conversationId, variant)
        val regenerated = base.copy(
            id = "sug_${UUID.randomUUID().toString().take(8)}",
            status = AIReplyStatus.READY,
            confidence = (base.confidence + 0.04f).coerceAtMost(0.95f),
            summaryZh = base.summaryZh + if (variant % 2 == 0) "（第 $variant 版，语气更主动）" else "（第 $variant 版，补充了后续跟进）",
            draftText = base.draftText + " " + followUpLine(conversation?.language ?: "en", variant),
            translatedText = base.translatedText + " " + followUpLineZh(variant),
        )
        _latest.update { it + (conversationId to regenerated) }
        return Result.success(regenerated)
    }

    override suspend fun acceptSuggestion(suggestionId: String): Result<AIReplySuggestion> {
        val found = _latest.value.values.firstOrNull { it.id == suggestionId }
            ?: return Result.failure(java.io.IOException("建议不存在"))
        val accepted = found.copy(status = AIReplyStatus.ACCEPTED)
        _latest.update { map -> map + (found.conversationId to accepted) }
        return Result.success(accepted)
    }

    override suspend fun dismissSuggestion(suggestionId: String) {
        _latest.update { map ->
            val found = map.values.firstOrNull { it.id == suggestionId } ?: return@update map
            map + (found.conversationId to found.copy(status = AIReplyStatus.DISMISSED))
        }
    }

    /** 未命中预置建议的会话：根据会话语言与产品即时生成通用建议 */
    private suspend fun buildGenericSuggestion(conversationId: String, variant: Int): AIReplySuggestion {
        val conversation: Conversation? =
            conversationRepository.getConversation(conversationId).getOrNull()
        val lang = conversation?.language ?: "en"
        val product = conversation?.product ?: "our products"
        val firstName = conversation?.customerName?.split(" ")?.firstOrNull() ?: "there"
        return when (lang) {
            "es" -> AIReplySuggestion(
                id = "sug_${UUID.randomUUID().toString().take(8)}",
                conversationId = conversationId,
                draftText = "Hola $firstName, gracias por su mensaje sobre $product. Para preparar una cotización precisa, ¿podría confirmar la cantidad requerida y el puerto de destino? Le responderemos con nuestra mejor oferta en 24 horas.",
                translatedText = "您好，感谢您关于 $product 的留言。为提供准确报价，请确认所需数量和目的港，我们将在 24 小时内回复最优价格。",
                suggestedLanguage = "es",
                intent = "通用询盘跟进",
                summaryZh = "请客户确认数量与目的港，承诺 24 小时内报价",
                riskLevel = RiskLevel.LOW,
                confidence = 0.6f,
                missingInformation = listOf("所需数量", "目的港"),
                citedKnowledge = listOf("产品规格书（通用）"),
                confirmReasons = emptyList(),
                status = AIReplyStatus.READY,
            )
            else -> AIReplySuggestion(
                id = "sug_${UUID.randomUUID().toString().take(8)}",
                conversationId = conversationId,
                draftText = "Hi $firstName, thanks for your message about $product." +
                    (if (variant > 0) " Following up on our last reply, could you also confirm the packaging preference?" else "") +
                    " To prepare an accurate quotation, could you confirm the required quantity and destination port? We will send our best offer within 24 hours.",
                translatedText = "您好，感谢您关于 $product 的留言。为提供准确报价，请确认所需数量和目的港，我们将在 24 小时内回复最优价格。",
                suggestedLanguage = "en",
                intent = "通用询盘跟进",
                summaryZh = "请客户确认数量与目的港，承诺 24 小时内报价",
                riskLevel = RiskLevel.LOW,
                confidence = 0.6f,
                missingInformation = listOf("所需数量", "目的港"),
                citedKnowledge = listOf("产品规格书（通用）"),
                confirmReasons = emptyList(),
                status = AIReplyStatus.READY,
            )
        }
    }

    private fun followUpLine(lang: String, variant: Int): String = when (lang) {
        "es" -> if (variant % 2 == 0) "Quedamos atentos a su confirmación." else "Si necesita más detalles, no dude en contactarnos."
        else -> if (variant % 2 == 0) "Looking forward to your confirmation." else "If you need more details, feel free to contact us anytime."
    }

    private fun followUpLineZh(variant: Int): String =
        if (variant % 2 == 0) "期待您的确认。" else "如需更多细节，欢迎随时联系我们。"
}
