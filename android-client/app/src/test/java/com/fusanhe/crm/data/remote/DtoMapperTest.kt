package com.fusanhe.crm.data.remote

import com.fusanhe.crm.data.remote.dto.AIReplyDraftDto
import com.fusanhe.crm.data.remote.dto.AccountDto
import com.fusanhe.crm.data.remote.dto.ExternalConversationDto
import com.fusanhe.crm.data.remote.dto.ExternalMessageDto
import com.fusanhe.crm.data.remote.mapper.toDomain
import com.fusanhe.crm.domain.model.Channel
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.model.MessageDirection
import com.fusanhe.crm.domain.model.RiskLevel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DtoMapperTest {
    @Test fun account_defaults_are_safe() {
        val customer = AccountDto(id = "a1", name = "Acme").toDomain()
        assertEquals("a1", customer.id)
        assertEquals("Acme", customer.companyName)
        assertTrue(customer.tags.isEmpty())
    }

    @Test fun conversation_maps_backend_states_and_unknown_fields_are_irrelevant() {
        val conversation = ExternalConversationDto(
            id = "c1", name = "Inquiry", status = "waitingApproval", channelType = "Alibaba", waitingMinutes = 130,
        ).toDomain()
        assertEquals(ConversationStatus.WAITING_REVIEW, conversation.status)
        assertEquals(Channel.ALIBABA, conversation.channel)
        assertTrue(conversation.slaBreached)
    }

    @Test fun message_and_draft_mapping_tolerate_missing_optional_values() {
        val message = ExternalMessageDto(id = "m1", body = "hello", direction = "outbound").toDomain("c1")
        assertEquals(MessageDirection.OUTGOING, message.direction)
        assertEquals("c1", message.conversationId)
        val draft = AIReplyDraftDto(draftId = "d1", riskLevel = "high", confidence = 5f).toDomain("c1")
        assertEquals(RiskLevel.HIGH, draft.riskLevel)
        assertEquals(1f, draft.confidence)
    }
}
