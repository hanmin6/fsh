package com.fusanhe.crm.ui.screens.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.model.DashboardData
import com.fusanhe.crm.domain.model.NotificationType
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.CustomerRepository
import com.fusanhe.crm.domain.repository.NotificationRepository
import com.fusanhe.crm.domain.repository.SessionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.buffer
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.stateIn
import java.util.Calendar
import javax.inject.Inject

sealed interface DashboardUiState {
    data object Loading : DashboardUiState
    data class Content(val data: DashboardData, val offline: Boolean) : DashboardUiState
    data class Error(val message: String) : DashboardUiState
}

@HiltViewModel
class DashboardViewModel @Inject constructor(
    customerRepository: CustomerRepository,
    conversationRepository: ConversationRepository,
    notificationRepository: NotificationRepository,
    sessionRepository: SessionRepository,
    private val mode: MockModeController,
) : ViewModel() {

    val currentUser = sessionRepository.currentUser

    private val refreshTrigger = MutableSharedFlow<Unit>(replay = 1)

    init {
        refreshTrigger.tryEmit(Unit)
    }

    val state: StateFlow<DashboardUiState> = refreshTrigger
        .flatMapLatest {
            combine(
                customerRepository.observeCustomers(),
                conversationRepository.observeConversations(),
                notificationRepository.observeNotifications(),
                mode.flags,
            ) { customers, conversations, notifications, flags ->
                if (flags.networkFailure || flags.offline) {
                    DashboardUiState.Error("网络连接失败，请检查网络后重试（演示模式）")
                } else {
                    val todayStart = todayStart()
                    DashboardUiState.Content(
                        data = DashboardData(
                            todayNewInquiries = conversations.count { it.lastMessageAt >= todayStart },
                            pendingReplies = conversations.count { it.status == ConversationStatus.WAITING_REPLY },
                            pendingReviews = conversations.count { it.status == ConversationStatus.WAITING_REVIEW },
                            overdueInquiries = conversations.count { it.slaBreached },
                            sendFailures = notifications.count { it.type == NotificationType.SEND_FAILURE },
                            recentCustomers = customers.sortedByDescending { it.lastContactAt ?: 0L }.take(3),
                            recentConversations = conversations.sortedByDescending { it.lastMessageAt }.take(3),
                            updatedAt = System.currentTimeMillis(),
                        ),
                        offline = false,
                    )
                }
            }
                .onStart {
                    emit(DashboardUiState.Loading)
                    delay(700)
                }
                .buffer(1)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), DashboardUiState.Loading)

    fun refresh() {
        refreshTrigger.tryEmit(Unit)
    }

    private fun todayStart(): Long = Calendar.getInstance().apply {
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }.timeInMillis
}
