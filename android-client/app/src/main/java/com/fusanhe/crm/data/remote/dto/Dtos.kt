package com.fusanhe.crm.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AccountDto(
    val id: String? = null,
    val name: String = "",
    val accountName: String? = null,
    @SerialName("sicCode") val country: String? = null,
    val emailAddress: String? = null,
    val phoneNumber: String? = null,
    val assignedUserName: String? = null,
    val description: String? = null,
    val createdAt: String? = null,
    val modifiedAt: String? = null,
)

@Serializable data class AccountListResponse(val total: Int = 0, val list: List<AccountDto> = emptyList())

@Serializable
data class AccountCreateRequest(
    val name: String,
    @SerialName("sicCode") val country: String? = null,
    val emailAddress: String? = null,
    val phoneNumber: String? = null,
    val description: String? = null,
)

@Serializable
data class ExternalConversationDto(
    val id: String? = null,
    val name: String = "",
    val subject: String? = null,
    val accountId: String? = null,
    val accountName: String? = null,
    val contactId: String? = null,
    val contactName: String? = null,
    val leadId: String? = null,
    val leadName: String? = null,
    val externalUserId: String? = null,
    val country: String? = null,
    val language: String? = null,
    val product: String? = null,
    val channelType: String? = null,
    val channelName: String? = null,
    val status: String = "",
    val assignedUserName: String? = null,
    val unreadCount: Int = 0,
    val lastMessageAt: String? = null,
    val lastMessagePreview: String? = null,
    val waitingMinutes: Long? = null,
)

@Serializable data class ExternalConversationListResponse(val total: Int = 0, val list: List<ExternalConversationDto> = emptyList())

@Serializable
data class ExternalMessageDto(
    val id: String? = null,
    val conversationId: String? = null,
    val body: String = "",
    val direction: String? = null,
    val senderName: String? = null,
    val language: String? = null,
    val sentAt: String? = null,
    val createdAt: String? = null,
    val deliveryStatus: String? = null,
)

@Serializable data class ExternalMessageListResponse(val total: Int = 0, val list: List<ExternalMessageDto> = emptyList())

@Serializable
data class AIReplyDraftDto(
    val id: String? = null,
    val draftId: String? = null,
    val conversationId: String? = null,
    val draftText: String = "",
    val translatedText: String = "",
    val status: String = "generated",
    val suggestedLanguage: String = "en",
    val intent: String = "",
    val summaryZh: String = "",
    val riskLevel: String = "low",
    val confidence: Float = 0f,
    val missingInformation: List<String> = emptyList(),
    val citedKnowledge: List<String> = emptyList(),
    val confirmReasons: List<String> = emptyList(),
)

@Serializable data class DraftApproveRequest(val draftText: String? = null)

@Serializable
data class DraftApproveResponse(
    val taskId: String? = null,
    val idempotencyKey: String? = null,
    val deduplicated: Boolean = false,
    val executionMode: String? = null,
)

@Serializable
data class AppUserDto(
    val id: String = "",
    val name: String = "",
    val userName: String? = null,
    val emailAddress: String? = null,
    val type: String? = null,
    val teamNames: Map<String, String> = emptyMap(),
)
