package com.fusanhe.crm.domain.model

/** 客户历史时间线条目类型 */
enum class HistoryType(val label: String) {
    INQUIRY("客户询盘"),
    REPLY("业务员回复"),
    AI_DRAFT("AI 回复草稿"),
    CALL("电话记录"),
    EMAIL("邮件记录"),
    WHATSAPP("WhatsApp 记录"),
    PROFILE_UPDATE("客户资料修改"),
    FOLLOW_UP_NOTE("跟进备注"),
    SEND_FAILURE("发送异常"),
}

enum class HistoryStatus(val label: String) {
    DONE("已完成"),
    PENDING("待处理"),
    FAILED("失败"),
    INFO("记录"),
}

/**
 * 客户历史时间线条目。
 */
data class CustomerHistoryItem(
    val id: String,
    val customerId: String,
    val type: HistoryType,
    val title: String,
    val content: String,
    val actorName: String,
    val channel: Channel? = null,
    val status: HistoryStatus = HistoryStatus.DONE,
    val occurredAt: Long,
    val aiAssisted: Boolean = false,
    /** 询盘类记录可跳转到会话详情 */
    val conversationId: String? = null,
)
