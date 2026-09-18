package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.DetectedLanguage
import com.fusanhe.crm.domain.model.Language
import com.fusanhe.crm.domain.model.TranslationResult
import com.fusanhe.crm.domain.repository.TranslationRepository
import kotlinx.coroutines.delay
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.random.Random

/**
 * 翻译仓库 Mock 实现：
 * - 模拟 500-1000ms 网络延迟
 * - 命中演示词典的文本返回真实感译文，其他文本返回演示占位译文
 * - 可通过设置页的"模拟翻译失败"开关演示失败重试
 */
@Singleton
class MockTranslationRepository @Inject constructor(
    private val mode: MockModeController,
) : TranslationRepository {

    override suspend fun detectLanguage(text: String): Result<DetectedLanguage> {
        delay(250)
        return Result.success(DetectedLanguage(detect(text), 0.92f))
    }

    override suspend fun translate(text: String, target: Language): Result<TranslationResult> {
        delay(Random.nextLong(500, 1000))
        if (mode.flags.value.translationFailure || mode.flags.value.offline) {
            return Result.failure(IOException("翻译服务暂时不可用（演示模式）"))
        }
        val source = detect(text)
        return Result.success(
            TranslationResult(
                originalText = text,
                translatedText = lookup(text, target),
                sourceLanguage = source,
                targetLanguage = target,
            )
        )
    }

    override suspend fun translateReply(text: String, target: Language): Result<TranslationResult> =
        translate(text, target)

    // ---- 内部实现 ----

    private fun detect(text: String): Language = when {
        text.any { it.code in 0x4E00..0x9FFF } -> Language.CHINESE
        text.any { it in "áéíóúñü¿¡ÁÉÍÓÚÑ" } -> Language.SPANISH
        else -> Language.ENGLISH
    }

    private fun lookup(text: String, target: Language): String {
        if (target == Language.CHINESE) {
            ZH_DICTIONARY[text.trim()]?.let { return it }
            ZH_DICTIONARY[text.trim().removeSuffix(".").removeSuffix("?")]?.let { return it }
            return "（演示译文）${text.trim()} —— Mock 机器翻译结果，仅供界面演示，请人工确认。"
        }
        if (target == Language.ENGLISH) {
            EN_DICTIONARY[text.trim()]?.let { return it }
        }
        if (target == Language.SPANISH) {
            ES_DICTIONARY[text.trim()]?.let { return it }
        }
        return "[Demo machine translation → ${target.label}] ${text.trim()}"
    }

    private companion object {
        // 客户消息（英/西/日/法）→ 中文
        val ZH_DICTIONARY = mapOf(
            "Please also confirm if you can print our brand on the jars." to "另请确认是否可以在瓶身印我们的品牌。",
            "Could you please update me on the exact ETD today?" to "能否今天告知确切的预计开船时间？",
            "Any update on the discount? I need to place the order this week." to "折扣有消息吗？我这周就要下单了。",
            "Thanks. And can you do retail packs of 100g with our design?" to "谢谢。可以做 100 克零售包装并使用我们的设计吗？",
        )

        // 常用语（中文）→ 英文
        val EN_DICTIONARY = mapOf(
            "您好，感谢您的询盘，我们会在 24 小时内提供详细报价。" to
                "Hello, thank you for your inquiry. We will provide a detailed quotation within 24 hours.",
            "我们的产品可提供 HALAL / ISO22000 / HACCP 认证。" to
                "Our products are certified with HALAL / ISO22000 / HACCP.",
            "常规 MOQ 为 1 吨，支持多规格混装。" to
                "Our regular MOQ is 1 ton, and mixed specifications are supported.",
            "交期一般为收到定金后 15-20 天。" to
                "The lead time is usually 15-20 days after receiving the deposit.",
            "我们可以先寄送样品，运费到付。" to
                "We can send samples first, with freight collected.",
            "感谢您的耐心等待，有任何问题随时联系我。" to
                "Thank you for your patience; feel free to contact me anytime.",
        )

        // 常用语（中文）→ 西班牙语
        val ES_DICTIONARY = mapOf(
            "您好，感谢您的询盘，我们会在 24 小时内提供详细报价。" to
                "Hola, gracias por su consulta. Le proporcionaremos una cotización detallada en 24 horas.",
            "我们的产品可提供 HALAL / ISO22000 / HACCP 认证。" to
                "Nuestros productos cuentan con certificación HALAL / ISO22000 / HACCP.",
            "常规 MOQ 为 1 吨，支持多规格混装。" to
                "El MOQ habitual es de 1 tonelada, admite especificaciones mixtas.",
            "交期一般为收到定金后 15-20 天。" to
                "El plazo de entrega suele ser de 15 a 20 días después del depósito.",
            "我们可以先寄送样品，运费到付。" to
                "Podemos enviar muestras primero, flete por cobrar.",
            "感谢您的耐心等待，有任何问题随时联系我。" to
                "Gracias por su paciencia; no dude en contactarme en cualquier momento.",
        )
    }
}
