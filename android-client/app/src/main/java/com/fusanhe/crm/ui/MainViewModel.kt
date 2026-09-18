package com.fusanhe.crm.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.SessionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

/** 应用级共享状态：底部导航未读徽标 + 登录态 */
@HiltViewModel
class MainViewModel @Inject constructor(
    conversationRepository: ConversationRepository,
    sessionRepository: SessionRepository,
) : ViewModel() {

    val isLoggedIn: StateFlow<Boolean> = sessionRepository.isLoggedIn

    /** 询盘 Tab 的未读总数徽标 */
    val unreadTotal: StateFlow<Int> = conversationRepository.observeConversations()
        .map { list -> list.sumOf { it.unreadCount } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)
}
