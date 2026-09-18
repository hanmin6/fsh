package com.fusanhe.crm.ui.screens.conversations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.repository.ConversationRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class ConversationFilter(val label: String) {
    ALL("全部"),
    WAITING_REPLY("待回复"),
    WAITING_REVIEW("待审核"),
    REPLIED("已回复"),
    CLOSED("已结束"),
}

data class ConversationListUiState(
    val conversations: List<Conversation> = emptyList(),
    val filter: ConversationFilter = ConversationFilter.ALL,
    val initialLoading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
    val offline: Boolean = false,
)

@HiltViewModel
class ConversationListViewModel @Inject constructor(
    private val conversationRepository: ConversationRepository,
    private val mode: MockModeController,
) : ViewModel() {

    private val _state = MutableStateFlow(ConversationListUiState())
    val state: StateFlow<ConversationListUiState> = _state.asStateFlow()

    private var all: List<Conversation> = emptyList()

    init {
        viewModelScope.launch {
            delay(700)
            conversationRepository.observeConversations().collect { list ->
                all = list
                applyFilter()
                _state.update {
                    it.copy(
                        initialLoading = false,
                        error = null,
                        offline = mode.flags.value.offline,
                    )
                }
            }
        }
    }

    fun refresh() {
        if (_state.value.refreshing) return
        viewModelScope.launch {
            _state.update { it.copy(refreshing = true, error = null) }
            conversationRepository.refresh()
                .onFailure { e ->
                    _state.update { it.copy(refreshing = false, error = e.message ?: "刷新失败") }
                }
                .onSuccess {
                    _state.update { it.copy(refreshing = false, offline = mode.flags.value.offline) }
                }
        }
    }

    fun setFilter(filter: ConversationFilter) {
        _state.update { it.copy(filter = filter) }
        applyFilter()
    }

    private fun applyFilter() {
        val current = _state.value
        val list = all
            .filter { current.filter == ConversationFilter.ALL || it.status.name == current.filter.name }
            .sortedByDescending { it.lastMessageAt }
        _state.update { it.copy(conversations = list) }
    }
}
