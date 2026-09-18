package com.fusanhe.crm.domain.model

/** 支持的翻译语言（演示阶段至少提供中文/英文/西班牙语） */
enum class Language(val code: String, val label: String) {
    CHINESE("zh", "中文"),
    ENGLISH("en", "英语 English"),
    SPANISH("es", "西班牙语 Español"),
    OTHER("other", "其他语言");

    companion object {
        fun fromCode(code: String?): Language =
            entries.firstOrNull { it.code == code } ?: OTHER
    }
}

data class DetectedLanguage(
    val language: Language,
    val confidence: Float,
)

data class TranslationResult(
    val originalText: String,
    val translatedText: String,
    val sourceLanguage: Language,
    val targetLanguage: Language,
)

/** 登录用户资料 */
data class UserProfile(
    val id: String,
    val name: String,
    val role: String,
    val department: String,
    val company: String,
    val email: String,
)

enum class NotificationType(val label: String) {
    SEND_FAILURE("发送异常"),
    SLA_TIMEOUT("超时提醒"),
    REVIEW_REMINDER("审核提醒"),
    SYSTEM("系统公告"),
}

enum class NotificationLevel { ERROR, WARNING, INFO }

data class AppNotificationItem(
    val id: String,
    val type: NotificationType,
    val title: String,
    val content: String,
    val occurredAt: Long,
    val level: NotificationLevel,
    val conversationId: String? = null,
    val customerId: String? = null,
    val read: Boolean = false,
)

/** 常用语 */
data class QuickPhrase(
    val id: String,
    val text: String,
    val category: String,
)

/** 知识资料（AI 回复引用来源） */
data class KnowledgeDocument(
    val id: String,
    val title: String,
    val category: String,
)

/** 工作台汇总数据 */
data class DashboardData(
    val todayNewInquiries: Int,
    val pendingReplies: Int,
    val pendingReviews: Int,
    val overdueInquiries: Int,
    val sendFailures: Int,
    val recentCustomers: List<Customer>,
    val recentConversations: List<Conversation>,
    val updatedAt: Long,
)

enum class ThemeMode(val label: String) {
    SYSTEM("跟随系统"),
    LIGHT("浅色"),
    DARK("深色"),
}

/** 设置页的演示控制开关 */
data class DemoFlags(
    val networkFailure: Boolean = false,
    val translationFailure: Boolean = false,
    val sendFailure: Boolean = false,
    val saveCustomerFailure: Boolean = false,
    val offline: Boolean = false,
) {
    val anyBlocking: Boolean get() = networkFailure || translationFailure || sendFailure || saveCustomerFailure || offline
}

enum class DemoFlag { NETWORK_FAILURE, TRANSLATION_FAILURE, SEND_FAILURE, SAVE_FAILURE, OFFLINE }
