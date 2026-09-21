package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.remote.api.CrmApiService
import com.fusanhe.crm.data.remote.dto.AccountCreateRequest
import com.fusanhe.crm.data.remote.dto.AccountDto
import com.fusanhe.crm.data.remote.dto.DraftApproveRequest
import com.fusanhe.crm.data.remote.mapper.toDomain
import com.fusanhe.crm.di.ApplicationScope
import com.fusanhe.crm.domain.model.AIReplyStatus
import com.fusanhe.crm.domain.model.AIReplySuggestion
import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerFilters
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.CustomerSortOption
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.NewCustomerInput
import com.fusanhe.crm.domain.repository.AIReplyRepository
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.CustomerRepository
import com.fusanhe.crm.domain.repository.SessionRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RemoteCustomerRepository @Inject constructor(
    private val api: CrmApiService,
    private val session: SessionRepository,
    @ApplicationScope appScope: CoroutineScope,
) : CustomerRepository {
    private val customers = MutableStateFlow<List<Customer>>(emptyList())
    init {
        appScope.launch {
            session.isLoggedIn.collectLatest { authenticated ->
                if (authenticated) refresh() else customers.value = emptyList()
            }
        }
    }

    override fun observeCustomers(): Flow<List<Customer>> = customers.asStateFlow()

    override suspend fun searchCustomers(query: String, filters: CustomerFilters, sort: CustomerSortOption): Result<List<Customer>> =
        runCatching {
            if (customers.value.isEmpty()) refresh().getOrThrow()
            val q = query.trim().lowercase()
            customers.value.asSequence()
                .filter { filters.countries.isEmpty() || it.country in filters.countries }
                .filter { filters.sources.isEmpty() || it.source in filters.sources }
                .filter { filters.owners.isEmpty() || it.ownerName in filters.owners }
                .filter { filters.levels.isEmpty() || it.level in filters.levels }
                .filter { q.isEmpty() || it.name.lowercase().contains(q) || it.companyName.lowercase().contains(q) || it.email?.lowercase()?.contains(q) == true }
                .let { sequence ->
                    when (sort) {
                        CustomerSortOption.LAST_CONTACT_DESC -> sequence.sortedByDescending { it.lastContactAt ?: 0L }
                        CustomerSortOption.CREATED_DESC -> sequence.sortedByDescending { it.createdAt }
                        CustomerSortOption.LEVEL -> sequence.sortedBy { it.level.ordinal }
                    }
                }.toList()
        }

    override suspend fun getCustomer(id: String): Result<Customer> = runCatching { api.getAccount(id).toDomain() }

    override suspend fun createCustomer(input: NewCustomerInput): Result<Customer> = runCatching {
        api.createAccount(AccountCreateRequest(
            name = input.companyName.ifBlank { input.name },
            country = input.country.ifBlank { null },
            emailAddress = input.email.ifBlank { null },
            phoneNumber = input.phone.ifBlank { null },
            description = input.notes.ifBlank { null },
        )).toDomain().also { created -> customers.update { listOf(created) + it } }
    }

    override suspend fun updateCustomer(customer: Customer): Result<Customer> = runCatching {
        api.updateAccount(customer.id, AccountDto(
            id = customer.id,
            name = customer.companyName.ifBlank { customer.name },
            country = customer.country,
            emailAddress = customer.email,
            phoneNumber = customer.phone,
            assignedUserName = customer.ownerName,
            description = customer.notes,
        )).toDomain().also { updated ->
            customers.update { list -> list.map { if (it.id == updated.id) updated else it } }
        }
    }

    override suspend fun getCustomerHistory(customerId: String): Result<List<CustomerHistoryItem>> = Result.success(emptyList())

    override suspend fun findPotentialDuplicates(input: NewCustomerInput): List<Customer> {
        val email = input.email.trim().lowercase()
        val phone = input.phone.filterNot { it.isWhitespace() }
        return customers.value.filter {
            it.name.equals(input.name.trim(), true) || it.companyName.equals(input.companyName.trim(), true) ||
                (email.isNotEmpty() && it.email?.lowercase() == email) ||
                (phone.isNotEmpty() && it.phone?.filterNot { char -> char.isWhitespace() } == phone)
        }
    }

    override suspend fun refresh(): Result<Unit> = runCatching {
        customers.value = api.getAccounts(maxSize = 100).list.map { it.toDomain() }
    }
}

@Singleton
class RemoteConversationRepository @Inject constructor(
    private val api: CrmApiService,
    private val session: SessionRepository,
    @ApplicationScope appScope: CoroutineScope,
) : ConversationRepository {
    private val conversations = MutableStateFlow<List<Conversation>>(emptyList())
    private val messages = MutableStateFlow<Map<String, List<Message>>>(emptyMap())
    private val drafts = MutableStateFlow<Map<String, String>>(emptyMap())
    init {
        appScope.launch {
            session.isLoggedIn.collectLatest { authenticated ->
                if (authenticated) refresh() else {
                    conversations.value = emptyList()
                    messages.value = emptyMap()
                    drafts.value = emptyMap()
                }
            }
        }
    }

    override fun observeConversations(): Flow<List<Conversation>> = conversations.asStateFlow()
    override suspend fun getConversation(id: String): Result<Conversation> = runCatching { api.getConversation(id).toDomain() }
    override fun observeMessages(conversationId: String): Flow<List<Message>> = messages.map { it[conversationId].orEmpty() }

    override suspend fun markAsRead(conversationId: String) {
        conversations.update { list -> list.map { if (it.id == conversationId) it.copy(unreadCount = 0) else it } }
        loadMessages(conversationId)
    }

    override fun observeDraft(conversationId: String): Flow<String> = drafts.map { it[conversationId].orEmpty() }
    override suspend fun saveLocalDraft(conversationId: String, text: String) { drafts.update { it + (conversationId to text) } }
    override suspend fun clearAllDrafts() { drafts.value = emptyMap() }

    override suspend fun sendMockMessage(conversationId: String, text: String, attachments: List<Attachment>): Result<Message> =
        Result.failure(IOException("真实模式禁止移动端直发；请使用草稿审核流程"))

    override suspend fun simulateIncomingMessage(conversationId: String) = Unit

    override suspend fun refresh(): Result<Unit> = runCatching {
        conversations.value = api.getConversations(maxSize = 100).list.map { it.toDomain() }
    }

    private suspend fun loadMessages(conversationId: String) {
        runCatching { api.getMessages(conversationId).list.map { it.toDomain(conversationId) } }
            .onSuccess { loaded -> messages.update { it + (conversationId to loaded) } }
    }
}

@Singleton
class RemoteAIReplyRepository @Inject constructor(
    private val api: CrmApiService,
    private val session: SessionRepository,
    @ApplicationScope appScope: CoroutineScope,
) : AIReplyRepository {
    private val latest = MutableStateFlow<Map<String, AIReplySuggestion>>(emptyMap())
    init {
        appScope.launch {
            session.isLoggedIn.collectLatest { authenticated ->
                if (!authenticated) latest.value = emptyMap()
            }
        }
    }
    override fun observeLatestSuggestion(conversationId: String): Flow<AIReplySuggestion?> = latest.map { it[conversationId] }

    override suspend fun generateSuggestion(conversationId: String): Result<AIReplySuggestion> = runCatching {
        api.generateReply(conversationId).toDomain(conversationId).also { suggestion -> latest.update { it + (conversationId to suggestion) } }
    }

    override suspend fun regenerateSuggestion(conversationId: String): Result<AIReplySuggestion> = generateSuggestion(conversationId)

    override suspend fun acceptSuggestion(suggestionId: String): Result<AIReplySuggestion> = runCatching {
        val found = latest.value.values.firstOrNull { it.id == suggestionId } ?: throw IOException("建议不存在")
        api.acceptDraft(suggestionId, DraftApproveRequest(found.draftText))
        found.copy(status = AIReplyStatus.ACCEPTED).also { accepted -> latest.update { it + (accepted.conversationId to accepted) } }
    }

    override suspend fun dismissSuggestion(suggestionId: String) {
        latest.update { map ->
            val found = map.values.firstOrNull { it.id == suggestionId } ?: return@update map
            map + (found.conversationId to found.copy(status = AIReplyStatus.DISMISSED))
        }
    }
}
