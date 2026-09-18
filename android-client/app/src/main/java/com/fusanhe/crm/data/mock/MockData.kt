package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.AIReplySuggestion
import com.fusanhe.crm.domain.model.AppNotificationItem
import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.KnowledgeDocument
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.QuickPhrase
import com.fusanhe.crm.domain.model.UserProfile

/** Mock 数据统一入口 */
object MockData {
    val currentUser: UserProfile get() = MockReference.currentUser
    val owners: List<String> get() = MockReference.owners
    val productPresets: List<String> get() = MockReference.productPresets
    val countries: List<String> get() = MockReference.countries
    val tagPresets: List<String> get() = MockReference.tagPresets
    val attachmentPresets: List<Attachment> get() = MockReference.attachmentPresets
    val quickPhrases: List<QuickPhrase> get() = MockReference.quickPhrases
    val knowledgeDocuments: List<KnowledgeDocument> get() = MockReference.knowledgeDocuments

    val customers: List<Customer> get() = MockCustomers.all
    val conversations: List<Conversation> get() = MockConversations.all
    fun messagesFor(conversationId: String): List<Message> =
        MockConversations.messagesByConversation[conversationId].orEmpty().sortedBy { it.sentAt }

    val history: List<CustomerHistoryItem> get() = MockHistory.all
    val suggestions: List<AIReplySuggestion> get() = MockAiSuggestions.all
    val notifications: List<AppNotificationItem> get() = MockReference.notifications
    val simulatedReplies: Map<String, List<Pair<String, String>>> get() = MockReference.simulatedReplies
}
