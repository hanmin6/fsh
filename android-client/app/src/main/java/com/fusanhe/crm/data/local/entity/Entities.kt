package com.fusanhe.crm.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room 本地缓存实体（占位）。
 * 当前阶段由 MockRepository 直接供数，Room 尚未在仓库实现中启用；
 * 接入真实后端时作为离线缓存层使用。
 */
@Entity(tableName = "customers")
data class CustomerEntity(
    @PrimaryKey val id: String,
    val name: String,
    val companyName: String,
    val country: String,
    val email: String?,
    val phone: String?,
    val whatsapp: String?,
    val source: String,
    val level: String,
    val ownerName: String,
    val tags: List<String>,
    val interestedProducts: List<String>,
    val notes: String?,
    val lastContactAt: Long?,
    val createdAt: Long,
)

@Entity(tableName = "conversations")
data class ConversationEntity(
    @PrimaryKey val id: String,
    val customerId: String,
    val channel: String,
    val subject: String,
    val status: String,
    val unreadCount: Int,
    val language: String,
    val product: String?,
    val lastMessageAt: Long,
    val lastMessagePreview: String,
    val waitingMinutes: Long,
    val slaBreached: Boolean,
)

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey val id: String,
    val conversationId: String,
    val direction: String,
    val senderName: String,
    val originalText: String,
    val translatedText: String?,
    val language: String,
    val sentAt: Long,
    val deliveryStatus: String,
    val attachments: List<String>,
    val aiAssisted: Boolean,
)
