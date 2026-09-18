package com.fusanhe.crm.ui.screens.customerdetail

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.model.Customer
import com.fusanhe.crm.domain.model.CustomerHistoryItem
import com.fusanhe.crm.domain.model.MessageDirection
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.CustomerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** 跟进概览数据 */
data class FollowUpSummary(
    val inquiryCount: Int,
    val waitingCount: Int,
    val lastReplyAt: Long?,
    val followStatus: String,
)

sealed interface CustomerDetailUiState {
    data object Loading : CustomerDetailUiState
    data class Content(
        val customer: Customer,
        val history: List<CustomerHistoryItem>,
        val followUp: FollowUpSummary,
    ) : CustomerDetailUiState

    data class Error(val message: String) : CustomerDetailUiState
}

@HiltViewModel
class CustomerDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val customerRepository: CustomerRepository,
    private val conversationRepository: ConversationRepository,
) : ViewModel() {

    private val customerId: String = checkNotNull(savedStateHandle["customerId"])

    private val _state = MutableStateFlow<CustomerDetailUiState>(CustomerDetailUiState.Loading)
    val state: StateFlow<CustomerDetailUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = CustomerDetailUiState.Loading
            val customer = customerRepository.getCustomer(customerId).getOrNull()
            if (customer == null) {
                _state.value = CustomerDetailUiState.Error("客户信息加载失败（演示模式）")
                return@launch
            }
            val history = customerRepository.getCustomerHistory(customerId).getOrDefault(emptyList())
            val conversations = conversationRepository.observeConversations().first()
                .filter { it.customerId == customerId }
            var lastReplyAt: Long? = null
            for (conversation in conversations) {
                val messages = conversationRepository.observeMessages(conversation.id).first()
                messages.lastOrNull { it.direction == MessageDirection.OUTGOING }?.let {
                    if (lastReplyAt == null || it.sentAt > lastReplyAt!!) lastReplyAt = it.sentAt
                }
            }
            val waitingCount = conversations.count { it.status == ConversationStatus.WAITING_REPLY }
            val followUp = FollowUpSummary(
                inquiryCount = conversations.size,
                waitingCount = waitingCount,
                lastReplyAt = lastReplyAt,
                followStatus = when {
                    waitingCount > 0 -> "待回复"
                    conversations.any { it.status == ConversationStatus.WAITING_REVIEW } -> "待审核 AI 回复"
                    conversations.isNotEmpty() -> "跟进中"
                    else -> "暂无询盘"
                },
            )
            _state.value = CustomerDetailUiState.Content(customer, history, followUp)
        }
    }
}
