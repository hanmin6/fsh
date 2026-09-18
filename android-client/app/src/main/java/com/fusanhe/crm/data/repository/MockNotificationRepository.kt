package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.domain.model.AppNotificationItem
import com.fusanhe.crm.domain.repository.NotificationRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import javax.inject.Inject
import javax.inject.Singleton

/** 通知仓库 Mock 实现 */
@Singleton
class MockNotificationRepository @Inject constructor() : NotificationRepository {

    private val _notifications = MutableStateFlow(MockData.notifications)
    override fun observeNotifications(): Flow<List<AppNotificationItem>> =
        _notifications.asStateFlow()

    override suspend fun markRead(id: String) {
        _notifications.update { list -> list.map { if (it.id == id) it.copy(read = true) else it } }
    }

    override suspend fun markAllRead() {
        _notifications.update { list -> list.map { it.copy(read = true) } }
    }
}
