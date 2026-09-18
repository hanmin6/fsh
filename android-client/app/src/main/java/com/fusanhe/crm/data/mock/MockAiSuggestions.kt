package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.AIReplyStatus
import com.fusanhe.crm.domain.model.AIReplySuggestion
import com.fusanhe.crm.domain.model.RiskLevel

/**
 * 演示用 AI 回复建议：5 条预置建议，覆盖价格/MOQ/交期/认证/折扣等
 * 需要"人工确认"的场景，以及不同风险等级。
 */
internal object MockAiSuggestions {

    val all: List<AIReplySuggestion> by lazy { build() }

    private fun build() = listOf(
        AIReplySuggestion(
            id = "sug01", conversationId = "conv01",
            draftText = "Dear John, thanks for confirming. Please find attached the PI for 12 tons of IQF blueberries at USD 3,150/ton CFR Long Beach, packing 10kg/carton. The crop year is 2026, and BRC/HACCP certificates are enclosed. Payment: 30% deposit, balance against B/L copy.",
            translatedText = "尊敬的 John，感谢确认。随函附上 12 吨 IQF 蓝莓的形式发票：单价 3,150 美元/吨，CFR 长滩，包装 10 公斤/箱。产季为 2026 年，随附 BRC/HACCP 证书。付款方式：30% 定金，见提单副本付尾款。",
            suggestedLanguage = "en", intent = "报价确认（PI 发送）",
            summaryZh = "确认价格、包装与 2026 产季，附证书与付款条款",
            riskLevel = RiskLevel.HIGH, confidence = 0.72f,
            missingInformation = listOf("客户未确认目的港清关代理", "未确认包装内衬要求"),
            citedKnowledge = listOf("IQF 蓝莓产品规格书 v3.2", "2026 年标准价格表（内部）"),
            confirmReasons = listOf("包含价格条款", "包含付款条款"),
            status = AIReplyStatus.READY,
        ),
        AIReplySuggestion(
            id = "sug02", conversationId = "conv02",
            draftText = "Hola Carlos, para 2 toneladas de fresa liofilizada podemos ofrecer un 3% de descuento sobre el precio FOB. MOQ 500 kg, entrega en 10 días. El certificado HALAL está incluido.",
            translatedText = "Carlos 您好，针对 2 吨冻干草莓，我们可以在 FOB 价格基础上提供 3% 折扣。MOQ 500 公斤，10 天内交货，随附 HALAL 证书。",
            suggestedLanguage = "es", intent = "催价与折扣申请",
            summaryZh = "针对 2 吨订单给予 3% 折扣并承诺 10 天交期",
            riskLevel = RiskLevel.MEDIUM, confidence = 0.68f,
            missingInformation = listOf("未确认目的港", "未确认付款方式"),
            citedKnowledge = listOf("冻干草莓产品规格书 v2.0", "2026 年标准价格表（内部）"),
            confirmReasons = listOf("包含折扣承诺", "包含 MOQ 条款"),
            status = AIReplyStatus.READY,
        ),
        AIReplySuggestion(
            id = "sug03", conversationId = "conv03",
            draftText = "Dear Anna, we sincerely apologize for the delay. The shipping documents are now at the bank, and the ETD is expected on September 14. We will share the full document set tomorrow morning and keep you updated daily.",
            translatedText = "尊敬的 Anna，对延误我们深表歉意。出货单据目前已提交银行，预计 9 月 14 日开船。明早我们会发送全套单据，并每日向您同步进展。",
            suggestedLanguage = "en", intent = "交期催促安抚",
            summaryZh = "致歉并告知预计开船时间与单据进度",
            riskLevel = RiskLevel.MEDIUM, confidence = 0.81f,
            missingInformation = listOf("ETD 需与货代最终确认"),
            citedKnowledge = listOf("常用物流方案与交期说明"),
            confirmReasons = listOf("包含交期承诺"),
            status = AIReplyStatus.READY,
        ),
        AIReplySuggestion(
            id = "sug04", conversationId = "conv04",
            draftText = "Hello Ahmed, the updated HALAL (valid until March 2027) and ISO22000 certificates are attached. OEM branding on jars is available with a minimum order of 3 tons per SKU.",
            translatedText = "Ahmed 您好，随附最新 HALAL（有效期至 2027 年 3 月）与 ISO22000 证书。瓶身 OEM 贴牌可用，每个 SKU 最小起订量为 3 吨。",
            suggestedLanguage = "en", intent = "认证文件与贴牌咨询",
            summaryZh = "发送认证证书并答复 OEM 贴牌起订量",
            riskLevel = RiskLevel.MEDIUM, confidence = 0.74f,
            missingInformation = listOf("OEM 贴牌起订量需与生产部确认"),
            citedKnowledge = listOf("出口认证一览（HALAL/ISO22000/HACCP/KOSHER）"),
            confirmReasons = listOf("涉及认证表述", "包含 MOQ 条款"),
            status = AIReplyStatus.READY,
        ),
        AIReplySuggestion(
            id = "sug05", conversationId = "conv05",
            draftText = "Hi Jack, as a valued quarterly partner we can offer 4% off the last price for your next container. This offer is valid until this Friday.",
            translatedText = "Jack 您好，作为我们的季度长期客户，下一柜可以在上次价格基础上给予 4% 折扣，该报价本周五前有效。",
            suggestedLanguage = "en", intent = "复购折扣申请",
            summaryZh = "针对长期客户给予 4% 复购折扣并限时",
            riskLevel = RiskLevel.HIGH, confidence = 0.66f,
            missingInformation = listOf("折扣需销售总监审批", "有效期需与生产排期核对"),
            citedKnowledge = listOf("2026 年标准价格表（内部）", "付款条款与信用政策"),
            confirmReasons = listOf("包含折扣承诺"),
            status = AIReplyStatus.READY,
        ),
    )
}
