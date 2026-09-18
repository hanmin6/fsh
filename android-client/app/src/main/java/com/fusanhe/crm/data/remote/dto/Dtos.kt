package com.fusanhe.crm.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * 与 EspoCRM 后端对应的网络 DTO（占位）。
 * 当前阶段未接入真实后端，仅供 Retrofit 接口定义与后续对接参考。
 * DTO 与领域模型之间的转换在接入真实 Repository 时补充 Mapper。
 */
@Serializable
data class AccountDto(
    val id: String? = null,
    val name: String = "",
    @SerialName("sicCode") val country: String? = null,
    @SerialName("emailAddress") val emailAddress: String? = null,
    @SerialName("phoneNumber") val phoneNumber: String? = null,
    @SerialName("assignedUserName") val assignedUserName: String? = null,
)

@Serializable
data class AccountListResponse(
    val total: Int = 0,
    val list: List<AccountDto> = emptyList(),
)

@Serializable
data class AccountCreateRequest(
    val name: String,
    @SerialName("sicCode") val country: String? = null,
    @SerialName("emailAddress") val emailAddress: String? = null,
    @SerialName("phoneNumber") val phoneNumber: String? = null,
)

@Serializable
data class ExternalConversationDto(
    val id: String? = null,
    val name: String = "",
    @SerialName("accountId") val accountId: String? = null,
    val status: String = "",
    @SerialName("assignedUserName") val assignedUserName: String? = null,
)

@Serializable
data class ExternalConversationListResponse(
    val total: Int = 0,
    val list: List<ExternalConversationDto> = emptyList(),
)

@Serializable
data class ExternalMessageDto(
    val id: String? = null,
    val body: String = "",
    @SerialName("isIncoming") val isIncoming: Boolean = false,
    @SerialName("createdAt") val createdAt: String? = null,
)

@Serializable
data class ExternalMessageSendRequest(
    @SerialName("conversationId") val conversationId: String,
    val body: String,
)

@Serializable
data class AIReplyDraftDto(
    val id: String? = null,
    @SerialName("draftBody") val draftBody: String = "",
    val status: String = "",
)

@Serializable
data class AIReplyGenerateRequest(
    @SerialName("conversationId") val conversationId: String,
    val instruction: String? = null,
)
