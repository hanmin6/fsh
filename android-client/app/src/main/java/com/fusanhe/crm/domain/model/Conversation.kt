package com.fusanhe.crm.domain.model

/** 沟通渠道 */
enum class Channel(val label: String) {
    EMAIL("邮件"),
    WHATSAPP("WhatsApp"),
    ALIBABA("阿里国际站"),
    MADE_IN_CHINA("Made-in-China"),
    WEBSITE("独立站"),
    PHONE("电话"),
}

enum class ConversationStatus(val label: String) {
    WAITING_REPLY("待回复"),
    WAITING_REVIEW("待审核"),
    REPLIED("已回复"),
    CLOSED("已结束"),
}

enum class OnlineStatus(val label: String) {
    ONLINE("在线"),
    RECENT_ACTIVE("最近活跃"),
    OFFLINE("离线"),
}

/**
 * 询盘会话（对应后端 ExternalConversation）。
 */
data class Conversation(
    val id: String,
    val customerId: String,
    val customerName: String,
    val companyName: String,
    val country: String,
    val channel: Channel,
    val subject: String,
    val status: ConversationStatus,
    val unreadCount: Int = 0,
    /** 客户使用的语言代码，如 en / es */
    val language: String,
    val product: String? = null,
    val lastMessageAt: Long = 0L,
    val lastMessagePreview: String = "",
    val waitingMinutes: Long = 0L,
    val slaBreached: Boolean = false,
    val onlineStatus: OnlineStatus = OnlineStatus.OFFLINE,
)

enum class MessageDirection { INCOMING, OUTGOING }

enum class DeliveryStatus(val label: String) {
    SENDING("发送中"),
    SENT("已送达"),
    FAILED("发送失败"),
    DRAFT("草稿"),
}

data class Attachment(
    val id: String,
    val name: String,
    val sizeLabel: String,
)

/**
 * 收发消息（对应后端 ExternalMessage）。
 */
data class Message(
    val id: String,
    val conversationId: String,
    val direction: MessageDirection,
    val senderName: String,
    /** 客户原文或业务员输入原文 */
    val originalText: String,
    /** 中文翻译（收到的消息）或翻译成客户语言的译文（发出的消息） */
    val translatedText: String? = null,
    val language: String,
    val sentAt: Long,
    val deliveryStatus: DeliveryStatus = DeliveryStatus.SENT,
    val attachments: List<Attachment> = emptyList(),
    val aiAssisted: Boolean = false,
)

/** 消息区原文/译文显示模式 */
enum class MessageDisplayMode(val label: String) {
    ORIGINAL_ONLY("仅原文"),
    ORIGINAL_WITH_TRANSLATION("原文+译文"),
}
