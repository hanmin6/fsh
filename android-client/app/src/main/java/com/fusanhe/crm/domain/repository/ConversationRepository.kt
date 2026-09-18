package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.Message
import kotlinx.coroutines.flow.Flow

interface ConversationRepository {
    fun observeConversations(): Flow<List<Conversation>>

    suspend fun getConversation(id: String): Result<Conversation>

    fun observeMessages(conversationId: String): Flow<List<Message>>

    suspend fun markAsRead(conversationId: String)

    fun observeDraft(conversationId: String): Flow<String>

    suspend fun saveLocalDraft(conversationId: String, text: String)

    suspend fun clearAllDrafts()

    /**
     * 演示阶段专用：仅更新本地 Mock 状态，不会发送到任何真实平台。
     */
    suspend fun sendMockMessage(
        conversationId: String,
        text: String,
        attachments: List<Attachment>,
    ): Result<Message>

    /** 演示：模拟客户发来一条新消息 */
    suspend fun simulateIncomingMessage(conversationId: String)

    /** 手动刷新（演示模式可模拟网络失败） */
    suspend fun refresh(): Result<Unit>
}
