package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.Channel
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.HistoryStatus
import com.fusanhe.crm.domain.model.HistoryType

/** 演示用客户历史时间线：24 条记录，覆盖全部类型 */
internal object MockHistory {

    val all: List<CustomerHistoryItem> by lazy { build() }

    private fun item(
        id: String, customerId: String, type: HistoryType, title: String, content: String,
        actorName: String, minAgo: Long, channel: Channel? = null,
        status: HistoryStatus = HistoryStatus.DONE, aiAssisted: Boolean = false,
        conversationId: String? = null,
    ) = CustomerHistoryItem(
        id = id, customerId = customerId, type = type, title = title, content = content,
        actorName = actorName, channel = channel, status = status, occurredAt = minutesAgo(minAgo),
        aiAssisted = aiAssisted, conversationId = conversationId,
    )

    private fun build() = listOf(
        // cus01 John Smith
        item("his01", "cus01", HistoryType.INQUIRY, "客户询盘：IQF 蓝莓 12-14mm",
            "寻购 A 级整果 IQF 蓝莓，20 尺整柜，要求报价与规格书。", "John Smith", 220,
            Channel.ALIBABA, conversationId = "conv01"),
        item("his02", "cus01", HistoryType.REPLY, "回复：发送规格书与整柜报价",
            "已发送 IQF 蓝莓规格书，并报价 CFR 长滩。", "张伟", 185, Channel.ALIBABA, aiAssisted = true),
        item("his03", "cus01", HistoryType.AI_DRAFT, "AI 草稿：PI 与产季确认",
            "AI 生成含价格与付款条款的回复草稿，等待人工审核。", "AI 助手", 35,
            Channel.ALIBABA, status = HistoryStatus.PENDING, aiAssisted = true, conversationId = "conv01"),
        item("his04", "cus01", HistoryType.PROFILE_UPDATE, "客户资料修改",
            "客户等级由 B 调整为 A；新增标签\"二次返单\"。", "张伟", 1440),
        // cus02 Anna Müller
        item("his05", "cus02", HistoryType.EMAIL, "邮件：订单 #FS-2608 交期沟通",
            "客户催促出货单据，已致歉并承诺次日上午答复。", "李娜", 1740, Channel.EMAIL),
        item("his06", "cus02", HistoryType.SEND_FAILURE, "邮件发送失败",
            "SMTP 超时，健康证书邮件未送达，需要重试。", "系统", 155, Channel.EMAIL, status = HistoryStatus.FAILED),
        item("his07", "cus02", HistoryType.FOLLOW_UP_NOTE, "跟进备注",
            "客户财务审批较慢，账期类报价需预留 1 周时间。", "李娜", 2880),
        // cus03 Carlos García
        item("his08", "cus03", HistoryType.INQUIRY, "客户询盘：冻干草莓片（西语）",
            "询问 FOB 价格与 MOQ，后续催促 2 吨折扣价，很急。", "Carlos García", 300,
            Channel.ALIBABA, conversationId = "conv02"),
        item("his09", "cus03", HistoryType.REPLY, "回复：FOB 价格单",
            "已发送 FOB 青岛价格单，客户进入砍价阶段。", "张伟", 290, Channel.ALIBABA),
        // cus04 María López
        item("his10", "cus04", HistoryType.CALL, "电话：年度框架意向沟通",
            "客户倾向签订年度框架协议，重点关心 CIF 瓦伦西亚运费。", "李娜", 3000, Channel.PHONE),
        item("his11", "cus04", HistoryType.INQUIRY, "客户询盘：65 Brix 浓缩橙汁",
            "需求 20 吨浓缩橙汁，要求 CIF 瓦伦西亚报价。", "María López", 1560,
            Channel.EMAIL, conversationId = "conv07"),
        // cus05 James Wilson
        item("his12", "cus05", HistoryType.EMAIL, "邮件：样品反馈",
            "客户确认样品质量良好，董事会后回复采购数量。", "王强", 2880, Channel.EMAIL),
        // cus06 Sophie Bernard
        item("his13", "cus06", HistoryType.EMAIL, "邮件：冻干草莓样品寄送",
            "已安排 DHL 寄送 500g 样品，运费到付。", "张伟", 1680, Channel.EMAIL),
        // cus07 Jack Thompson
        item("his14", "cus07", HistoryType.WHATSAPP, "WhatsApp：复购折扣申请",
            "客户申请下一柜 5% 折扣，需销售总监审批。", "王强", 390, Channel.WHATSAPP,
            status = HistoryStatus.PENDING, conversationId = "conv05"),
        // cus08 佐藤
        item("his15", "cus08", HistoryType.EMAIL, "邮件：大蒜粉规格确认",
            "已提供粒度 100-120 目规格与农残检测报告。", "李娜", 78, Channel.EMAIL),
        // cus09 Ahmed
        item("his16", "cus09", HistoryType.INQUIRY, "客户询盘：HALAL / ISO 认证",
            "确认蜂蜜订单前要求提供 HALAL 与 ISO22000 证书。", "Ahmed Al-Mansoori", 130,
            Channel.WHATSAPP, conversationId = "conv04"),
        item("his17", "cus09", HistoryType.WHATSAPP, "WhatsApp：OEM 贴牌咨询",
            "客户询问瓶身贴牌，需确认最小起订量。", "张伟", 50, Channel.WHATSAPP),
        // cus10 Emily Carter
        item("his18", "cus10", HistoryType.REPLY, "回复：30g 零售装方案",
            "已答复 30g 零售袋装方案，MOQ 5000 袋。", "李娜", 2880, Channel.EMAIL),
        // cus11 Linda van Dijk
        item("his19", "cus11", HistoryType.INQUIRY, "客户询盘：番茄酱复购 2 柜",
            "复购 28-30 Brix 番茄酱，要求 60 天账期。", "Linda van Dijk", 70,
            Channel.ALIBABA, conversationId = "conv09"),
        item("his20", "cus11", HistoryType.SEND_FAILURE, "消息发送失败",
            "账期方案回复发送失败，消息未送达客户。", "系统", 38, Channel.ALIBABA,
            status = HistoryStatus.FAILED, conversationId = "conv09"),
        // cus12 Oliver Brown
        item("his21", "cus12", HistoryType.CALL, "电话：价格目标差异",
            "客户对比多家供应商后认为价格偏高，暂时搁置。", "张伟", 7200, Channel.PHONE),
        // 补充记录
        item("his22", "cus01", HistoryType.WHATSAPP, "WhatsApp：产季与包装确认",
            "客户确认包装 10kg/箱，询问 2026 产季。", "张伟", 36, Channel.WHATSAPP),
        item("his23", "cus09", HistoryType.FOLLOW_UP_NOTE, "跟进备注",
            "计划在 Gulfood 展会当面洽谈年度合同，准备样品箱。", "张伟", 240),
        item("his24", "cus03", HistoryType.PROFILE_UPDATE, "客户资料修改",
            "新增标签\"价格敏感\"；西班牙语为首选沟通语言。", "张伟", 4320),
    )
}
