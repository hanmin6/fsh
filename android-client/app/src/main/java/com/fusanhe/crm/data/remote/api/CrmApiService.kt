package com.fusanhe.crm.data.remote.api

import com.fusanhe.crm.data.remote.dto.AccountCreateRequest
import com.fusanhe.crm.data.remote.dto.AccountDto
import com.fusanhe.crm.data.remote.dto.AccountListResponse
import com.fusanhe.crm.data.remote.dto.AIReplyDraftDto
import com.fusanhe.crm.data.remote.dto.AIReplyGenerateRequest
import com.fusanhe.crm.data.remote.dto.ExternalConversationDto
import com.fusanhe.crm.data.remote.dto.ExternalConversationListResponse
import com.fusanhe.crm.data.remote.dto.ExternalMessageDto
import com.fusanhe.crm.data.remote.dto.ExternalMessageSendRequest
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * EspoCRM 后端 API 占位接口（base: http://localhost:8080/api/v1）。
 *
 * 当前阶段【不会】调用这些接口：Hilt 中绑定的全部是 Mock Repository。
 * 接入真实后端时，实现 RemoteRepository 并在 DataModule 中替换绑定即可，
 * UI 与 ViewModel 无需改动。字段映射详见 docs/BACKEND_API_MAPPING.md。
 */
interface CrmApiService {

    // ---- 客户（Account / Contact / Lead） ----

    @GET("Account")
    suspend fun getAccounts(
        @Query("offset") offset: Int = 0,
        @Query("maxSize") maxSize: Int = 20,
        @Query("orderBy") orderBy: String = "createdAt",
        @Query("order") order: String = "desc",
    ): AccountListResponse

    @GET("Account/{id}")
    suspend fun getAccount(@Path("id") id: String): AccountDto

    @POST("Account")
    suspend fun createAccount(@Body body: AccountCreateRequest): AccountDto

    @PUT("Account/{id}")
    suspend fun updateAccount(@Path("id") id: String, @Body body: AccountDto): AccountDto

    // ---- 询盘会话（ExternalConversation） ----

    @GET("ExternalConversation")
    suspend fun getConversations(
        @Query("offset") offset: Int = 0,
        @Query("maxSize") maxSize: Int = 20,
        @Query("orderBy") orderBy: String = "lastMessageAt",
    ): ExternalConversationListResponse

    @GET("ExternalConversation/{id}")
    suspend fun getConversation(@Path("id") id: String): ExternalConversationDto

    // ---- 消息（ExternalMessage） ----

    @GET("ExternalConversation/{id}/externalMessages")
    suspend fun getMessages(
        @Path("id") conversationId: String,
        @Query("offset") offset: Int = 0,
        @Query("maxSize") maxSize: Int = 50,
    ): List<ExternalMessageDto>

    @POST("ExternalMessage")
    suspend fun sendMessage(@Body body: ExternalMessageSendRequest): ExternalMessageDto

    // ---- AI 回复草稿（AIReplyDraft） ----

    @POST("AIReplyDraft/action/generateReply")
    suspend fun generateReply(@Body body: AIReplyGenerateRequest): AIReplyDraftDto

    @POST("AIReplyDraft/{id}")
    suspend fun acceptDraft(@Path("id") id: String, @Body body: AIReplyDraftDto): AIReplyDraftDto
}
