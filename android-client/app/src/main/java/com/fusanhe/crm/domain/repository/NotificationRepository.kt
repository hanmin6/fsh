package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.AppNotificationItem
import kotlinx.coroutines.flow.Flow

interface NotificationRepository {
    fun observeNotifications(): Flow<List<AppNotificationItem>>
    suspend fun markRead(id: String)
    suspend fun markAllRead()
}
