package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.data.mock.now
import com.fusanhe.crm.di.ApplicationScope
import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.model.DeliveryStatus
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.MessageDirection
import com.fusanhe.crm.domain.repository.ConversationRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.IOException
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 询盘会话仓库 Mock 实现。
 *
 * - 会话与消息保存在内存中，进程存活期间状态不丢失（屏幕旋转、页面切换安全）
 * - sendMockMessage 仅更新本地状态，绝不发送到真实平台
 * - 内置定时器周期性模拟客户发来新消息
 */
@Singleton
class MockConversationRepository @Inject constructor(
    private val mode: MockModeController,
    @ApplicationScope appScope: CoroutineScope,
) : ConversationRepository {

    private val _conversations = MutableStateFlow(MockData.conversations)
    override fun observeConversations(): Flow<List<Conversation>> = _conversations.asStateFlow()

    private val _messages = MutableStateFlow(
        MockData.conversations.associate { it.id to MockData.messagesFor(it.id) }
    )

    private val _drafts = MutableStateFlow<Map<String, String>>(emptyMap())

    private var incomingCounter = 0

    init {
        // 每 75 秒模拟一条客户新消息，让未读数与列表保持"实时"感
        appScope.launch {
            while (isActive) {
                delay(75_000)
                val candidates = _conversations.value.filter { it.status != ConversationStatus.CLOSED }
                if (candidates.isNotEmpty()) {
                    simulateIncomingMessage(candidates.random().id)
                }
            }
        }
    }

    override suspend fun getConversation(id: String): Result<Conversation> {
        delay(250)
        val flags = mode.flags.value
        if (flags.networkFailure || flags.offline) {
            return Result.failure(IOException("网络连接失败（演示模式）"))
        }
        val conversation = _conversations.value.firstOrNull { it.id == id }
            ?: return Result.failure(IOException("会话不存在"))
        return Result.success(conversation)
    }

    override fun observeMessages(conversationId: String): Flow<List<Message>> =
        _messages.asStateFlow().map { map ->
            map[conversationId].orEmpty().sortedBy { it.sentAt }
        }

    override suspend fun markAsRead(conversationId: String) {
        _conversations.update { list ->
            list.map { if (it.id == conversationId && it.unreadCount > 0) it.copy(unreadCount = 0) else it }
        }
    }

    override fun observeDraft(conversationId: String): Flow<String> =
        _drafts.asStateFlow().map { it[conversationId].orEmpty() }

    override suspend fun saveLocalDraft(conversationId: String, text: String) {
        _drafts.update { it + (conversationId to text) }
    }

    override suspend fun clearAllDrafts() {
        _drafts.value = emptyMap()
    }

    override suspend fun sendMockMessage(
        conversationId: String,
        text: String,
        attachments: List<Attachment>,
    ): Result<Message> {
        val conversation = _conversations.value.firstOrNull { it.id == conversationId }
            ?: return Result.failure(IOException("会话不存在"))

        val sending = Message(
            id = "msg_${UUID.randomUUID().toString().take(8)}",
            conversationId = conversationId,
            direction = MessageDirection.OUTGOING,
            senderName = MockData.currentUser.name,
            originalText = text,
            translatedText = null,
            language = conversation.language,
            sentAt = now(),
            deliveryStatus = DeliveryStatus.SENDING,
            attachments = attachments,
        )
        appendMessage(sending)
        touchConversation(conversationId, preview = text, fromCustomer = false)
        delay(900)

        val flags = mode.flags.value
        if (flags.sendFailure || flags.offline) {
            val failed = sending.copy(deliveryStatus = DeliveryStatus.FAILED)
            replaceMessage(failed)
            return Result.failure(IOException("发送失败，请检查网络后重试（演示模式）"))
        }
        val sent = sending.copy(deliveryStatus = DeliveryStatus.SENT)
        replaceMessage(sent)
        return Result.success(sent)
    }

    override suspend fun simulateIncomingMessage(conversationId: String) {
        val conversation = _conversations.value.firstOrNull { it.id == conversationId }
            ?: return
        val poolKey = if (MockData.simulatedReplies.containsKey(conversation.language)) {
            conversation.language
        } else {
            "other"
        }
        val pool = MockData.simulatedReplies.getValue(poolKey)
        val (original, zh) = pool[incomingCounter++ % pool.size]
        val message = Message(
            id = "msg_${UUID.randomUUID().toString().take(8)}",
            conversationId = conversationId,
            direction = MessageDirection.INCOMING,
            senderName = conversation.customerName,
            originalText = original,
            translatedText = zh,
            language = conversation.language,
            sentAt = now(),
            deliveryStatus = DeliveryStatus.SENT,
        )
        appendMessage(message)
        _conversations.update { list ->
            list.map { c ->
                if (c.id == conversationId) {
                    c.copy(
                        unreadCount = c.unreadCount + 1,
                        lastMessageAt = message.sentAt,
                        lastMessagePreview = original,
                        waitingMinutes = 0,
                        slaBreached = false,
                        status = if (c.status == ConversationStatus.CLOSED) ConversationStatus.WAITING_REPLY else c.status,
                    )
                } else {
                    c
                }
            }
        }
    }

    override suspend fun refresh(): Result<Unit> {
        delay(500)
        val flags = mode.flags.value
        if (flags.networkFailure || flags.offline) {
            return Result.failure(IOException("网络连接失败（演示模式）"))
        }
        return Result.success(Unit)
    }

    private fun appendMessage(message: Message) {
        _messages.update { map ->
            val list = map[message.conversationId].orEmpty() + message
            map + (message.conversationId to list.sortedBy { it.sentAt })
        }
    }

    private fun replaceMessage(message: Message) {
        _messages.update { map ->
            map + (message.conversationId to map[message.conversationId].orEmpty().map {
                if (it.id == message.id) message else it
            })
        }
    }

    private fun touchConversation(conversationId: String, preview: String, fromCustomer: Boolean) {
        _conversations.update { list ->
            list.map { c ->
                if (c.id == conversationId) {
                    c.copy(
                        lastMessageAt = now(),
                        lastMessagePreview = preview,
                        unreadCount = if (fromCustomer) c.unreadCount + 1 else 0,
                        status = if (fromCustomer && c.status != ConversationStatus.CLOSED) {
                            ConversationStatus.WAITING_REPLY
                        } else if (!fromCustomer && c.status != ConversationStatus.CLOSED) {
                            ConversationStatus.REPLIED
                        } else {
                            c.status
                        },
                    )
                } else {
                    c
                }
            }
        }
    }
}
