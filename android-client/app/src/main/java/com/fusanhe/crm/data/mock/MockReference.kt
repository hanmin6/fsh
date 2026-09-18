package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.AppNotificationItem
import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.KnowledgeDocument
import com.fusanhe.crm.domain.model.NotificationLevel
import com.fusanhe.crm.domain.model.NotificationType
import com.fusanhe.crm.domain.model.QuickPhrase
import com.fusanhe.crm.domain.model.UserProfile

/** 常用参考数据：用户、下拉选项、常用语、知识库、通知、演示回复池 */
internal object MockReference {

    val currentUser = UserProfile(
        id = "u001", name = "张伟", role = "外贸业务员", department = "销售一部",
        company = "福三和食品有限公司", email = "zhangwei@fusanhe.com",
    )

    val owners = listOf("张伟", "李娜", "王强")

    /** 产品预设（新增客户"感兴趣的产品"多选） */
    val productPresets = listOf(
        "冻结蓝莓", "冻干草莓", "浓缩橙汁", "苹果脆片", "番茄酱 28-30%",
        "槐花蜂蜜", "混合坚果", "速冻菠菜", "脱水大蒜粉", "果蔬脆片",
    )

    val countries = listOf(
        "美国", "德国", "英国", "西班牙", "墨西哥", "巴西", "澳大利亚", "日本", "韩国",
        "印度", "阿联酋", "加拿大", "法国", "意大利", "荷兰", "沙特阿拉伯", "泰国", "越南",
        "菲律宾", "印度尼西亚", "马来西亚", "智利", "阿根廷", "波兰", "土耳其", "埃及",
        "南非", "俄罗斯", "其他",
    )

    val tagPresets = listOf(
        "重点客户", "二次返单", "认证关注", "价格敏感", "大客户", "新客户", "展会线索", "零售包装",
    )

    val attachmentPresets = listOf(
        Attachment("preset01", "IQF蓝莓规格书.pdf", "1.2 MB"),
        Attachment("preset02", "出口认证一览.pdf", "860 KB"),
        Attachment("preset03", "报价单-2026Q4.xlsx", "54 KB"),
        Attachment("preset04", "农残检测报告.pdf", "2.1 MB"),
    )

    val quickPhrases = listOf(
        QuickPhrase("qp01", "您好，感谢您的询盘，我们会在 24 小时内提供详细报价。", "开场"),
        QuickPhrase("qp02", "我们的产品可提供 HALAL / ISO22000 / HACCP 认证。", "认证"),
        QuickPhrase("qp03", "常规 MOQ 为 1 吨，支持多规格混装。", "MOQ"),
        QuickPhrase("qp04", "交期一般为收到定金后 15-20 天。", "交期"),
        QuickPhrase("qp05", "我们可以先寄送样品，运费到付。", "样品"),
        QuickPhrase("qp06", "感谢您的耐心等待，有任何问题随时联系我。", "跟进"),
    )

    val knowledgeDocuments = listOf(
        KnowledgeDocument("kd01", "IQF 蓝莓产品规格书 v3.2", "产品规格"),
        KnowledgeDocument("kd02", "出口认证一览（HALAL/ISO22000/HACCP/KOSHER）", "认证资质"),
        KnowledgeDocument("kd03", "2026 年标准价格表（内部）", "价格"),
        KnowledgeDocument("kd04", "付款条款与信用政策", "商务条款"),
        KnowledgeDocument("kd05", "常用物流方案与交期说明", "物流交期"),
    )

    val notifications: List<AppNotificationItem> by lazy {
        listOf(
            AppNotificationItem("ntf01", NotificationType.SEND_FAILURE, "邮件发送失败：Anna Müller",
                "订单交期邮件 SMTP 超时，未送达，请重试发送。", minutesAgo(155),
                NotificationLevel.ERROR, conversationId = "conv03", customerId = "cus02"),
            AppNotificationItem("ntf02", NotificationType.SEND_FAILURE, "阿里国际站消息发送失败：Linda van Dijk",
                "60 天账期回复发送失败，消息未送达客户。", minutesAgo(38),
                NotificationLevel.ERROR, conversationId = "conv09", customerId = "cus11"),
            AppNotificationItem("ntf03", NotificationType.SLA_TIMEOUT, "询盘即将超时：Carlos García",
                "等待回复已 95 分钟（SLA 2 小时），请尽快回复。", minutesAgo(60),
                NotificationLevel.WARNING, conversationId = "conv02", customerId = "cus03"),
            AppNotificationItem("ntf04", NotificationType.SLA_TIMEOUT, "询盘超时提醒：佐藤 健一",
                "等待回复已超过 60 分钟。", minutesAgo(30),
                NotificationLevel.WARNING, conversationId = "conv11", customerId = "cus08"),
            AppNotificationItem("ntf05", NotificationType.REVIEW_REMINDER, "AI 草稿待审核：John Smith",
                "AI 已生成蓝莓 PI 回复草稿，包含价格条款，请人工确认。", minutesAgo(34),
                NotificationLevel.INFO, conversationId = "conv01", customerId = "cus01"),
            AppNotificationItem("ntf06", NotificationType.REVIEW_REMINDER, "AI 草稿待审核：Jack Thompson",
                "AI 草稿包含折扣承诺，风险等级：高。", minutesAgo(24),
                NotificationLevel.INFO, conversationId = "conv05", customerId = "cus07"),
            AppNotificationItem("ntf07", NotificationType.SYSTEM, "知识库更新：《2026 年标准价格表》",
                "新增 3 个 SKU 价格，AI 回复将自动引用最新版本。", hoursAgo(2),
                NotificationLevel.INFO),
            AppNotificationItem("ntf08", NotificationType.SYSTEM, "当前为 UI 演示模式",
                "本应用所有数据均为本地 Mock，不会发送真实消息。", hoursAgo(8),
                NotificationLevel.INFO),
        )
    }

    /** "模拟客户回复"演示数据池：按语言分组（原文 to 中文翻译） */
    val simulatedReplies: Map<String, List<Pair<String, String>>> = mapOf(
        "en" to listOf(
            "Thanks for the quick reply. Could you also share the latest certificates?" to
                "感谢尽快回复。能否同时提供最新的证书？",
            "Sounds good. Please send the PI when it is ready." to
                "听起来不错。形式发票准备好后请发送给我。",
            "Got it. What about the lead time for the next shipment?" to
                "明白了。下一批货的交期是多久？",
            "OK, noted. We will confirm the order details this week." to
                "好的，收到。我们这周内确认订单细节。",
        ),
        "es" to listOf(
            "Gracias por la respuesta. ¿Puede enviarme el catálogo completo?" to
                "感谢回复。可以发我完整的产品目录吗？",
            "Perfecto, quedo atento a la cotización final." to
                "好的，我等您的最终报价。",
            "Entendido. ¿Cuál sería el tiempo de entrega?" to
                "明白了。交货时间是多久？",
        ),
        "fr" to listOf(
            "Merci pour votre réponse rapide." to "感谢您的快速回复。",
            "D'accord, j'attends le devis final." to "好的，我等最终报价。",
        ),
        "ja" to listOf(
            "ありがとうございます。検討してまた連絡します。" to "非常感谢。我们考虑后再联系您。",
            "承知しました。見積りをお待ちしています。" to "知道了，我们等您的报价。",
        ),
        "other" to listOf(
            "Thank you, noted with thanks." to "谢谢，已收到并知悉。",
            "OK, we will get back to you soon." to "好的，我们会尽快回复您。",
        ),
    )
}
