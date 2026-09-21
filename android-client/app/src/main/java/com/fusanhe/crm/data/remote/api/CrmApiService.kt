package com.fusanhe.crm.data.remote.api

import com.fusanhe.crm.data.remote.dto.AccountCreateRequest
import com.fusanhe.crm.data.remote.dto.AccountDto
import com.fusanhe.crm.data.remote.dto.AccountListResponse
import com.fusanhe.crm.data.remote.dto.AIReplyDraftDto
import com.fusanhe.crm.data.remote.dto.AppUserDto
import com.fusanhe.crm.data.remote.dto.DraftApproveRequest
import com.fusanhe.crm.data.remote.dto.DraftApproveResponse
import com.fusanhe.crm.data.remote.dto.ExternalConversationDto
import com.fusanhe.crm.data.remote.dto.ExternalConversationListResponse
import com.fusanhe.crm.data.remote.dto.ExternalMessageDto
import com.fusanhe.crm.data.remote.dto.ExternalMessageListResponse
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * EspoCRM production API. Channel sending is intentionally absent.
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
    ): ExternalMessageListResponse

    // ---- AI 回复草稿（AIReplyDraft） ----

    @POST("Fusanhe/conversation/{id}/generate-draft")
    suspend fun generateReply(@Path("id") conversationId: String): AIReplyDraftDto

    @POST("Fusanhe/draft/{id}/approve")
    suspend fun acceptDraft(@Path("id") id: String, @Body body: DraftApproveRequest): DraftApproveResponse

    @GET("App/user")
    suspend fun getCurrentUser(): AppUserDto
}
