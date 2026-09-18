package com.fusanhe.crm.ui.screens.notifications

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.domain.model.AppNotificationItem
import com.fusanhe.crm.domain.repository.NotificationRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

data class NotificationsUiState(
    val loading: Boolean = true,
    val items: List<AppNotificationItem> = emptyList(),
    val unreadCount: Int = 0,
)

@HiltViewModel
class NotificationsViewModel @Inject constructor(
    private val notificationRepository: NotificationRepository,
) : ViewModel() {

    val state: StateFlow<NotificationsUiState> =
        notificationRepository.observeNotifications()
            .map { list ->
                NotificationsUiState(
                    loading = false,
                    items = list.sortedByDescending { it.occurredAt },
                    unreadCount = list.count { !it.read },
                )
            }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), NotificationsUiState())

    fun markRead(id: String) {
        viewModelScope.launch { notificationRepository.markRead(id) }
    }

    fun markAllRead() {
        viewModelScope.launch { notificationRepository.markAllRead() }
    }
}
