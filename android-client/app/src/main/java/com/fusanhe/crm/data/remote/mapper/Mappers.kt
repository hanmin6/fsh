package com.fusanhe.crm.data.remote.mapper

import com.fusanhe.crm.data.remote.dto.AIReplyDraftDto
import com.fusanhe.crm.data.remote.dto.AccountDto
import com.fusanhe.crm.data.remote.dto.ExternalConversationDto
import com.fusanhe.crm.data.remote.dto.ExternalMessageDto
import com.fusanhe.crm.domain.model.AIReplyStatus
import com.fusanhe.crm.domain.model.AIReplySuggestion
import com.fusanhe.crm.domain.model.Channel
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerLevel
import com.fusanhe.crm.domain.model.CustomerSource
import com.fusanhe.crm.domain.model.DeliveryStatus
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.MessageDirection
import com.fusanhe.crm.domain.model.OnlineStatus
import com.fusanhe.crm.domain.model.RiskLevel
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

fun AccountDto.toDomain(): Customer = Customer(
    id = id.orEmpty(),
    name = name.ifBlank { accountName.orEmpty() },
    companyName = accountName ?: name,
    country = country.orEmpty(),
    email = emailAddress,
    phone = phoneNumber,
    source = CustomerSource.MANUAL,
    level = CustomerLevel.C,
    ownerName = assignedUserName.orEmpty(),
    notes = description,
    lastContactAt = parseEpoch(modifiedAt),
    createdAt = parseEpoch(createdAt) ?: 0L,
)

fun ExternalConversationDto.toDomain(): Conversation {
    val customerId = accountId ?: contactId ?: leadId ?: externalUserId.orEmpty()
    val customerName = accountName ?: contactName ?: leadName ?: externalUserId ?: "未知客户"
    val wait = waitingMinutes ?: 0L
    return Conversation(
        id = id.orEmpty(),
        customerId = customerId,
        customerName = customerName,
        companyName = accountName ?: customerName,
        country = country.orEmpty(),
        channel = channel(channelType ?: channelName),
        subject = subject ?: name,
        status = conversationStatus(status),
        unreadCount = unreadCount,
        language = language ?: "en",
        product = product,
        lastMessageAt = parseEpoch(lastMessageAt) ?: 0L,
        lastMessagePreview = lastMessagePreview.orEmpty(),
        waitingMinutes = wait,
        slaBreached = wait >= 120,
        onlineStatus = OnlineStatus.OFFLINE,
    )
}

fun ExternalMessageDto.toDomain(fallbackConversationId: String): Message = Message(
    id = id.orEmpty(),
    conversationId = conversationId ?: fallbackConversationId,
    direction = if (direction.equals("outbound", true)) MessageDirection.OUTGOING else MessageDirection.INCOMING,
    senderName = senderName.orEmpty(),
    originalText = body,
    language = language ?: "en",
    sentAt = parseEpoch(sentAt ?: createdAt) ?: 0L,
    deliveryStatus = when (deliveryStatus?.lowercase()) {
        "failed" -> DeliveryStatus.FAILED
        "sending" -> DeliveryStatus.SENDING
        "draft" -> DeliveryStatus.DRAFT
        else -> DeliveryStatus.SENT
    },
)

fun AIReplyDraftDto.toDomain(fallbackConversationId: String): AIReplySuggestion = AIReplySuggestion(
    id = draftId ?: id.orEmpty(),
    conversationId = conversationId ?: fallbackConversationId,
    draftText = draftText,
    translatedText = translatedText,
    suggestedLanguage = suggestedLanguage,
    intent = intent,
    summaryZh = summaryZh,
    riskLevel = when (riskLevel.lowercase()) {
        "high" -> RiskLevel.HIGH
        "medium" -> RiskLevel.MEDIUM
        else -> RiskLevel.LOW
    },
    confidence = confidence.coerceIn(0f, 1f),
    missingInformation = missingInformation,
    citedKnowledge = citedKnowledge,
    confirmReasons = confirmReasons,
    status = when (status.lowercase()) {
        "approved", "accepted" -> AIReplyStatus.ACCEPTED
        "failed" -> AIReplyStatus.FAILED
        else -> AIReplyStatus.READY
    },
)

private fun channel(value: String?): Channel = when (value?.lowercase()) {
    "alibaba" -> Channel.ALIBABA
    "madeinchina", "made-in-china" -> Channel.MADE_IN_CHINA
    "website" -> Channel.WEBSITE
    "whatsapp" -> Channel.WHATSAPP
    "phone" -> Channel.PHONE
    else -> when {
        value?.contains("alibaba", true) == true -> Channel.ALIBABA
        value?.contains("made", true) == true -> Channel.MADE_IN_CHINA
        value?.contains("whatsapp", true) == true -> Channel.WHATSAPP
        value?.contains("website", true) == true -> Channel.WEBSITE
        else -> Channel.EMAIL
    }
}

private fun conversationStatus(value: String): ConversationStatus = when (value.lowercase()) {
    "waitingapproval", "drafted", "readytosend" -> ConversationStatus.WAITING_REVIEW
    "replied", "sent" -> ConversationStatus.REPLIED
    "closed" -> ConversationStatus.CLOSED
    else -> ConversationStatus.WAITING_REPLY
}

internal fun parseEpoch(value: String?): Long? {
    if (value.isNullOrBlank()) return null
    return runCatching { Instant.parse(value).toEpochMilli() }.getOrElse {
        runCatching {
            LocalDateTime.parse(value, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))
                .toInstant(ZoneOffset.UTC).toEpochMilli()
        }.getOrNull()
    }
}
