package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Channel
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.model.DeliveryStatus
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.MessageDirection
import com.fusanhe.crm.domain.model.OnlineStatus

/** 演示用会话与消息数据：15 个会话、50+ 条双语消息 */
internal object MockConversations {

    val all: List<Conversation> by lazy { buildConversations() }

    val messagesByConversation: Map<String, List<Message>> by lazy { buildMessages() }

    private fun msg(
        convId: String,
        idx: Int,
        incoming: Boolean,
        senderName: String,
        lang: String,
        minAgo: Long,
        original: String,
        translated: String?,
        aiAssisted: Boolean = false,
        status: DeliveryStatus = DeliveryStatus.SENT,
        attachments: List<Attachment> = emptyList(),
    ) = Message(
        id = "${convId}_m$idx",
        conversationId = convId,
        direction = if (incoming) MessageDirection.INCOMING else MessageDirection.OUTGOING,
        senderName = senderName,
        originalText = original,
        translatedText = translated,
        language = lang,
        sentAt = minutesAgo(minAgo),
        deliveryStatus = status,
        attachments = attachments,
        aiAssisted = aiAssisted,
    )

    private fun buildConversations() = listOf(
        Conversation(
            id = "conv01", customerId = "cus01", customerName = "John Smith",
            companyName = "Summit Foods LLC", country = "美国", channel = Channel.ALIBABA,
            subject = "IQF 蓝莓报价与规格", status = ConversationStatus.WAITING_REVIEW,
            unreadCount = 0, language = "en", product = "冻结蓝莓",
            lastMessageAt = minutesAgo(35), lastMessagePreview = "Also, can you confirm the crop year is 2026?",
            waitingMinutes = 35, slaBreached = false, onlineStatus = OnlineStatus.RECENT_ACTIVE,
        ),
        Conversation(
            id = "conv02", customerId = "cus03", customerName = "Carlos García",
            companyName = "Distribuidora García S.A. de C.V.", country = "墨西哥", channel = Channel.ALIBABA,
            subject = "冻干草莓报价 / MOQ（西语）", status = ConversationStatus.WAITING_REPLY,
            unreadCount = 2, language = "es", product = "冻干草莓",
            lastMessageAt = minutesAgo(90), lastMessagePreview = "También necesito certificado HALAL.",
            waitingMinutes = 95, slaBreached = true, onlineStatus = OnlineStatus.RECENT_ACTIVE,
        ),
        Conversation(
            id = "conv03", customerId = "cus02", customerName = "Anna Müller",
            companyName = "Bavaria Food Trading GmbH", country = "德国", channel = Channel.EMAIL,
            subject = "苹果脆片交期催促", status = ConversationStatus.WAITING_REPLY,
            unreadCount = 1, language = "en", product = "苹果脆片",
            lastMessageAt = minutesAgo(160), lastMessagePreview = "Could you please update me on the exact ETD today?",
            waitingMinutes = 160, slaBreached = true, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv04", customerId = "cus09", customerName = "Ahmed Al-Mansoori",
            companyName = "Gulf Foodstuff Trading LLC", country = "阿联酋", channel = Channel.WHATSAPP,
            subject = "HALAL / ISO 认证文件", status = ConversationStatus.WAITING_REPLY,
            unreadCount = 1, language = "en", product = "槐花蜂蜜",
            lastMessageAt = minutesAgo(50), lastMessagePreview = "Please also confirm if you can print our brand on the jars.",
            waitingMinutes = 50, slaBreached = false, onlineStatus = OnlineStatus.ONLINE,
        ),
        Conversation(
            id = "conv05", customerId = "cus07", customerName = "Jack Thompson",
            companyName = "Outback Fresh Imports", country = "澳大利亚", channel = Channel.WHATSAPP,
            subject = "复购折扣申请", status = ConversationStatus.WAITING_REVIEW,
            unreadCount = 0, language = "en", product = "冻结蓝莓",
            lastMessageAt = minutesAgo(25), lastMessagePreview = "Any update on the discount? I need to place the order this week.",
            waitingMinutes = 25, slaBreached = false, onlineStatus = OnlineStatus.RECENT_ACTIVE,
        ),
        Conversation(
            id = "conv06", customerId = "cus01", customerName = "John Smith",
            companyName = "Summit Foods LLC", country = "美国", channel = Channel.ALIBABA,
            subject = "冻干草莓：糖度与零售包装", status = ConversationStatus.WAITING_REPLY,
            unreadCount = 1, language = "en", product = "冻干草莓",
            lastMessageAt = minutesAgo(10), lastMessagePreview = "Thanks. And can you do retail packs of 100g with our design?",
            waitingMinutes = 10, slaBreached = false, onlineStatus = OnlineStatus.ONLINE,
        ),
        Conversation(
            id = "conv07", customerId = "cus04", customerName = "María López",
            companyName = "Grupo Alimentario López", country = "西班牙", channel = Channel.EMAIL,
            subject = "浓缩橙汁 65 Brix 询价（西语）", status = ConversationStatus.REPLIED,
            unreadCount = 0, language = "es", product = "浓缩橙汁",
            lastMessageAt = hoursAgo(20), lastMessagePreview = "La cotización es CIF Valencia, incluyendo el flete marítimo.",
            waitingMinutes = 0, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv08", customerId = "cus05", customerName = "James Wilson",
            companyName = "Wilson & Sons Trading", country = "英国", channel = Channel.EMAIL,
            subject = "蜂蜜样品反馈", status = ConversationStatus.REPLIED,
            unreadCount = 0, language = "en", product = "槐花蜂蜜",
            lastMessageAt = daysAgo(2), lastMessagePreview = "We will come back with volumes after the board meeting next week.",
            waitingMinutes = 0, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv09", customerId = "cus11", customerName = "Linda van Dijk",
            companyName = "Van Dijk Food Services B.V.", country = "荷兰", channel = Channel.ALIBABA,
            subject = "番茄酱复购 + 60 天账期", status = ConversationStatus.WAITING_REVIEW,
            unreadCount = 0, language = "en", product = "番茄酱 28-30%",
            lastMessageAt = minutesAgo(40), lastMessagePreview = "Please include payment terms 60 days this time.",
            waitingMinutes = 40, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv10", customerId = "cus06", customerName = "Sophie Bernard",
            companyName = "Bernard Import France", country = "法国", channel = Channel.EMAIL,
            subject = "冻干草莓样品申请（法语）", status = ConversationStatus.REPLIED,
            unreadCount = 0, language = "fr", product = "冻干草莓",
            lastMessageAt = hoursAgo(27), lastMessagePreview = "Merci beaucoup!",
            waitingMinutes = 0, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv11", customerId = "cus08", customerName = "佐藤 健一",
            companyName = "Sato Trading Co., Ltd.", country = "日本", channel = Channel.EMAIL,
            subject = "大蒜粉规格确认（日语）", status = ConversationStatus.WAITING_REPLY,
            unreadCount = 1, language = "ja", product = "脱水大蒜粉",
            lastMessageAt = minutesAgo(75), lastMessagePreview = "有難うございます。輸送中の温度管理は可能ですか。",
            waitingMinutes = 75, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv12", customerId = "cus10", customerName = "Emily Carter",
            companyName = "Maple Import Foods", country = "加拿大", channel = Channel.EMAIL,
            subject = "30g 零售装草莓脆", status = ConversationStatus.REPLIED,
            unreadCount = 0, language = "en", product = "冻干草莓",
            lastMessageAt = daysAgo(2), lastMessagePreview = "We offer 30g retail pouches with an MOQ of 5,000 bags.",
            waitingMinutes = 0, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv13", customerId = "cus12", customerName = "Oliver Brown",
            companyName = "Brown Brothers Wholesale", country = "英国", channel = Channel.PHONE,
            subject = "混合坚果年度合同", status = ConversationStatus.CLOSED,
            unreadCount = 0, language = "en", product = "混合坚果",
            lastMessageAt = daysAgo(5), lastMessagePreview = "Thanks for the feedback; if your budget adjusts, we are always here.",
            waitingMinutes = 0, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv14", customerId = "cus02", customerName = "Anna Müller",
            companyName = "Bavaria Food Trading GmbH", country = "德国", channel = Channel.EMAIL,
            subject = "清关文件：健康证书", status = ConversationStatus.REPLIED,
            unreadCount = 0, language = "en", product = "苹果脆片",
            lastMessageAt = hoursAgo(4), lastMessagePreview = "The Health Certificate has been scanned and sent.",
            waitingMinutes = 0, slaBreached = false, onlineStatus = OnlineStatus.OFFLINE,
        ),
        Conversation(
            id = "conv15", customerId = "cus09", customerName = "Ahmed Al-Mansoori",
            companyName = "Gulf Foodstuff Trading LLC", country = "阿联酋", channel = Channel.WHATSAPP,
            subject = "迪拜 Gulfood 展会约见", status = ConversationStatus.WAITING_REPLY,
            unreadCount = 1, language = "en", product = "混合坚果",
            lastMessageAt = minutesAgo(20), lastMessagePreview = "See you at Gulfood next month. Booth number?",
            waitingMinutes = 20, slaBreached = false, onlineStatus = OnlineStatus.ONLINE,
        ),
    )

    private fun buildMessages(): Map<String, List<Message>> {
        val list = mutableListOf<Message>()

        // conv01: John Smith - IQF 蓝莓（英文）
        list += msg("conv01", 1, true, "John Smith", "en", 220,
            "Hi, we are looking for IQF blueberries, 12-14mm, for our retail brand. Could you send your specification and best price for 20ft FCL?",
            "您好，我们在寻找 IQF 速冻蓝莓，果径 12-14mm，用于我们的零售品牌。能否提供规格书和 20 尺整柜最优价？")
        list += msg("conv01", 2, false, "张伟", "en", 210,
            "您好 John，感谢询盘。我们的 IQF 蓝莓规格齐全，规格书今天发您，请查收。",
            "Hi John, thank you for your inquiry. We have a full range of IQF blueberry specs; the spec sheet will be sent today.", aiAssisted = true)
        list += msg("conv01", 3, true, "John Smith", "en", 205,
            "Great. We need Grade A, whole fruit, no added sugar. What is your MOQ and lead time?",
            "很好。我们需要 A 级整果、无添加糖。MOQ 和交期是多少？")
        list += msg("conv01", 4, false, "张伟", "en", 195,
            "MOQ 为 1 个 20 尺柜（约 12 吨），交期为收到定金后 15-20 天。",
            "MOQ is one 20ft container (about 12 tons); lead time is 15-20 days after deposit.")
        list += msg("conv01", 5, true, "John Smith", "en", 190,
            "Please also quote CFR Long Beach.", "另请报 CFR 长滩港价格。")
        list += msg("conv01", 6, false, "张伟", "en", 185,
            "CFR 长滩参考价 3,150 美元/吨，随函附 BRC、HACCP 证书副本。",
            "Reference price CFR Long Beach USD 3,150/ton, with copies of BRC and HACCP certificates.", aiAssisted = true)
        list += msg("conv01", 7, true, "John Smith", "en", 40,
            "Price looks workable. Please send PI with packaging 10kg/carton.",
            "价格可以接受。请发送形式发票，包装按 10 公斤/箱。")
        list += msg("conv01", 8, true, "John Smith", "en", 35,
            "Also, can you confirm the crop year is 2026?", "另外，请确认是否为 2026 年产季？")

        // conv02: Carlos García - 冻干草莓（西班牙语）
        list += msg("conv02", 1, true, "Carlos García", "es", 300,
            "Hola, me interesa fresa liofilizada en rodajas. ¿Puede enviarme precio FOB y MOQ?",
            "您好，我对冻干草莓片感兴趣。可以提供 FOB 价格和最小起订量吗？")
        list += msg("conv02", 2, false, "张伟", "es", 290,
            "您好 Carlos，冻干草莓片 FOB 青岛价格单已发送，请查收。",
            "Hola Carlos, le he enviado la lista de precios FOB Qingdao de fresa liofilizada en rodajas.")
        list += msg("conv02", 3, true, "Carlos García", "es", 280,
            "Gracias. ¿Tienen disponibilidad para 500 kg? ¿Cuál es el tiempo de entrega?",
            "谢谢。500 公斤有货吗？交货时间是多久？")
        list += msg("conv02", 4, false, "张伟", "es", 270,
            "500 公斤有现货，交期 7 天以内。",
            "Tenemos 500 kg en stock; la entrega es en un plazo de 7 días.")
        list += msg("conv02", 5, true, "Carlos García", "es", 95,
            "Necesito el precio final con descuento para 2 toneladas, por favor. Es urgente.",
            "请给我 2 吨的最终折扣价，很急。")
        list += msg("conv02", 6, true, "Carlos García", "es", 90,
            "También necesito certificado HALAL.", "另外我还需要 HALAL 证书。")

        // conv03: Anna Müller - 苹果脆片交期催促（英文）
        list += msg("conv03", 1, true, "Anna Müller", "en", hoursToMin(30),
            "Dear team, our order #FS-2608 (apple chips) was promised for Sept 10. We still have not received the shipping documents.",
            "您好，我们的订单 #FS-2608（苹果脆片）承诺 9 月 10 日交货，但至今未收到出货单据。",
            attachments = listOf(Attachment("att01", "PO_FS-2608.pdf", "248 KB")))
        list += msg("conv03", 2, false, "李娜", "en", hoursToMin(29),
            "非常抱歉，单据银行流程延迟，我们正在跟进，明天上午给您答复。",
            "Our apologies; the bank document process was delayed. We are following up and will reply tomorrow morning.")
        list += msg("conv03", 3, true, "Anna Müller", "en", hoursToMin(27),
            "This delay is causing problems with our client. Please treat it as urgent.",
            "这次延误已经影响到我们的客户，请务必加急处理。")
        list += msg("conv03", 4, true, "Anna Müller", "en", 160,
            "Could you please update me on the exact ETD today?", "能否今天告知确切的预计开船时间？")

        // conv04: Ahmed - HALAL / ISO 认证（英文）
        list += msg("conv04", 1, true, "Ahmed Al-Mansoori", "en", 130,
            "Hello, before we confirm the honey order, please share HALAL and ISO22000 certificates.",
            "您好，确认蜂蜜订单之前，请提供 HALAL 和 ISO22000 证书。")
        list += msg("conv04", 2, false, "张伟", "en", 120,
            "您好 Ahmed，证书今天更新后发您，HALAL 证书有效期到 2027 年 3 月。",
            "Hello Ahmed, we will send the updated certificates today. The HALAL certificate is valid until March 2027.",
            aiAssisted = true)
        list += msg("conv04", 3, true, "Ahmed Al-Mansoori", "en", 50,
            "Please also confirm if you can print our brand on the jars.",
            "另请确认是否可以在瓶身印我们的品牌。")

        // conv05: Jack Thompson - 复购折扣（英文）
        list += msg("conv05", 1, true, "Jack Thompson", "en", hoursToMin(6),
            "Mate, we have been ordering every quarter. Can you do 5% off the last price for the next container?",
            "老朋友，我们每个季度都下单，下一柜能在上次价格基础上打 95 折吗？")
        list += msg("conv05", 2, false, "王强", "en", hoursToMin(5),
            "感谢长期支持，我去申请一下折扣政策，稍后回复您。",
            "Thanks for your continued support; let me check the discount policy and get back to you.")
        list += msg("conv05", 3, true, "Jack Thompson", "en", 25,
            "Any update on the discount? I need to place the order this week.",
            "折扣有消息吗？我这周就要下单了。")

        // conv06: John Smith - 冻干草莓规格（英文，消息缺少完整规格）
        list += msg("conv06", 1, true, "John Smith", "en", 180,
            "For the freeze-dried strawberry slices, what brix do you use before freezing?",
            "冻干草莓片在冻干前的糖度（brix）是多少？")
        list += msg("conv06", 2, false, "张伟", "en", 170,
            "原料糖度 8-10 brix，冻干后水分 ≤3%。",
            "Raw material brix is 8-10; moisture after freeze-drying is 3% max.")
        list += msg("conv06", 3, true, "John Smith", "en", 10,
            "Thanks. And can you do retail packs of 100g with our design?",
            "谢谢。可以做 100 克零售包装并使用我们的设计吗？")

        // conv07: María López - 浓缩橙汁（西班牙语）
        list += msg("conv07", 1, true, "María López", "es", hoursToMin(26),
            "Buenas tardes, necesitamos cotización de concentrado de naranja 65 brix, 20 toneladas.",
            "下午好，我们需要 65 糖度浓缩橙汁 20 吨的报价。")
        list += msg("conv07", 2, false, "李娜", "es", hoursToMin(25),
            "María 您好，65 brix 浓缩橙汁 20 吨报价已发送至您的邮箱。",
            "Buenas tardes María, la cotización de 20 toneladas de concentrado de naranja 65 brix ha sido enviada.",
            aiAssisted = true)
        list += msg("conv07", 3, true, "María López", "es", hoursToMin(22),
            "Gracias. ¿El precio incluye transporte hasta Valencia?",
            "谢谢。价格包含到瓦伦西亚的运输吗？")
        list += msg("conv07", 4, false, "李娜", "es", hoursToMin(20),
            "报价为 CIF 瓦伦西亚，已含海运费。",
            "La cotización es CIF Valencia, incluyendo el flete marítimo.")

        // conv08: James Wilson - 蜂蜜样品（英文）
        list += msg("conv08", 1, true, "James Wilson", "en", hoursToMin(72),
            "We received the honey samples. Overall quality looks good.",
            "蜂蜜样品已收到，整体质量不错。")
        list += msg("conv08", 2, false, "王强", "en", hoursToMin(60),
            "很高兴样品符合预期，如需正式报价随时联系。",
            "Glad the samples meet your expectations; feel free to contact us for a formal quotation.")
        list += msg("conv08", 3, true, "James Wilson", "en", hoursToMin(48),
            "We will come back with volumes after the board meeting next week.",
            "下周董事会之后我们会回复具体数量。")

        // conv09: Linda van Dijk - 番茄酱复购（英文）
        list += msg("conv09", 1, true, "Linda van Dijk", "en", 70,
            "Hi, we want to reorder tomato paste brix 28-30%, 2 containers, same as last year.",
            "您好，我们想复购 28-30 糖度番茄酱 2 柜，和去年一样。")
        list += msg("conv09", 2, false, "王强", "en", 60,
            "收到，规格单和最新价格稍后发您。",
            "Noted; I will send the spec sheet and latest prices shortly.")
        list += msg("conv09", 3, true, "Linda van Dijk", "en", 40,
            "Please include payment terms 60 days this time.",
            "这次请提供 60 天账期的付款条件。")
        list += msg("conv09", 4, false, "王强", "en", 38,
            "60 天账期需要向财务申请，我先答复您方案。",
            "The 60-day payment terms need approval from our finance team; I will reply with a proposal first.",
            status = DeliveryStatus.FAILED)

        // conv10: Sophie Bernard - 冻干草莓样品（法语）
        list += msg("conv10", 1, true, "Sophie Bernard", "fr", hoursToMin(30),
            "Bonjour, pourriez-vous envoyer des échantillons de fraises lyophilisées 500g?",
            "您好，可以寄 500 克冻干草莓样品给我们吗？")
        list += msg("conv10", 2, false, "张伟", "fr", hoursToMin(28),
            "样品已安排 DHL 寄出，运费到付，3-5 天送达。",
            "Bonjour, les échantillons seront envoyés par DHL, frais à votre charge, livraison en 3-5 jours.")
        list += msg("conv10", 3, true, "Sophie Bernard", "fr", hoursToMin(27),
            "Merci beaucoup!", "非常感谢！")

        // conv11: 佐藤 - 大蒜粉（日语）
        list += msg("conv11", 1, true, "佐藤 健一", "ja", 80,
            "にんにく粉の粒度と残留農薬検査成績表を送っていただけますか。",
            "可以提供大蒜粉的粒度规格和农残检测报告吗？")
        list += msg("conv11", 2, false, "李娜", "ja", 78,
            "粒度 100-120 目，农残检测报告随规格书一起附上，请查收。",
            "粒度は100-120メッシュです。農薬検査成績表は仕様書と共にお送りします。")
        list += msg("conv11", 3, true, "佐藤 健一", "ja", 75,
            "有難うございます。輸送中の温度管理は可能ですか。",
            "谢谢。运输过程中可以控温吗？")

        // conv12: Emily Carter - 零售装（英文）
        list += msg("conv12", 1, true, "Emily Carter", "en", hoursToMin(72),
            "Do you offer freeze-dried strawberry chips in 30g retail packs?",
            "你们提供 30 克零售装的冻干草莓脆吗？")
        list += msg("conv12", 2, false, "李娜", "en", hoursToMin(48),
            "支持 30g 零售袋装，起订量 5000 袋。",
            "We offer 30g retail pouches with an MOQ of 5,000 bags.")

        // conv13: Oliver Brown - 年度合同（英文，电话渠道，已结束）
        list += msg("conv13", 1, true, "Oliver Brown", "en", daysToMin(6),
            "We compared several suppliers; your price is above our target.",
            "我们比较了几家供应商，你们的价格高于我们的目标价。")
        list += msg("conv13", 2, false, "张伟", "en", daysToMin(5),
            "感谢反馈，如预算调整欢迎随时联系。",
            "Thanks for the feedback; if your budget adjusts, we are always here.")

        // conv14: Anna Müller - 清关文件（英文）
        list += msg("conv14", 1, true, "Anna Müller", "en", hoursToMin(20),
            "Customs asked for the Health Certificate. Could you send it?",
            "海关要求提供健康证书，可以发给我们吗？")
        list += msg("conv14", 2, false, "李娜", "en", hoursToMin(4),
            "健康证书已扫描发送，正本随单据一起邮寄。",
            "The Health Certificate has been scanned and sent; the original will be couriered with the documents.")

        // conv15: Ahmed - 展会约见（英文）
        list += msg("conv15", 1, true, "Ahmed Al-Mansoori", "en", 20,
            "See you at Gulfood next month. Booth number?", "下个月迪拜 Gulfood 展会见，展位号是多少？")
        list += msg("conv15", 2, false, "张伟", "en", 55,
            "我们在 PB 展区 D28 展位，欢迎来样品交流。",
            "We will be at Booth D28 in Hall PB; you are welcome to visit us for samples.",
            aiAssisted = true)

        return list.groupBy { it.conversationId }
            .mapValues { (_, v) -> v.sortedBy { it.sentAt } }
    }

    private fun hoursToMin(h: Long): Long = h * 60

    private fun daysToMin(d: Long): Long = d * 60 * 24
}
