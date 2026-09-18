package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.AIReplySuggestion
import kotlinx.coroutines.flow.Flow

interface AIReplyRepository {
    fun observeLatestSuggestion(conversationId: String): Flow<AIReplySuggestion?>

    suspend fun generateSuggestion(conversationId: String): Result<AIReplySuggestion>

    suspend fun regenerateSuggestion(conversationId: String): Result<AIReplySuggestion>

    suspend fun acceptSuggestion(suggestionId: String): Result<AIReplySuggestion>

    suspend fun dismissSuggestion(suggestionId: String)
}
