package com.fusanhe.crm.data.remote

import com.fusanhe.crm.data.remote.api.CrmApiService
import com.fusanhe.crm.data.remote.mapper.toDomain
import com.fusanhe.crm.domain.model.ConversationStatus
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class CrmApiServiceTest {
    private lateinit var server: MockWebServer
    private lateinit var api: CrmApiService

    @Before fun setup() {
        server = MockWebServer().apply { start() }
        api = Retrofit.Builder()
            .baseUrl(server.url("/api/v1/"))
            .addConverterFactory(Json { ignoreUnknownKeys = true }
                .asConverterFactory("application/json".toMediaType()))
            .build().create(CrmApiService::class.java)
    }

    @After fun teardown() { server.shutdown() }

    @Test fun list_route_and_unknown_payload_fields_are_tolerated() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""
            {"total":1,"unexpected":"future","list":[{"id":"c1","name":"Inquiry","status":"futureState","extra":42}]}
        """.trimIndent()))
        val result = api.getConversations()
        assertEquals("/api/v1/ExternalConversation?offset=0&maxSize=20&orderBy=lastMessageAt", server.takeRequest().path)
        assertEquals(ConversationStatus.WAITING_REPLY, result.list.single().toDomain().status)
    }

    @Test fun draft_generation_uses_real_custom_route() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json")
            .setBody("{\"draftId\":\"d1\",\"draftText\":\"Hello\"}"))
        val draft = api.generateReply("conv-1")
        assertEquals("d1", draft.draftId)
        assertEquals("/api/v1/Fusanhe/conversation/conv-1/generate-draft", server.takeRequest().path)
    }
}
