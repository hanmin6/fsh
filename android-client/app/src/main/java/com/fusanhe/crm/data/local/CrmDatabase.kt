package com.fusanhe.crm.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import com.fusanhe.crm.data.local.dao.ConversationDao
import com.fusanhe.crm.data.local.dao.CustomerDao
import com.fusanhe.crm.data.local.dao.MessageDao
import com.fusanhe.crm.data.local.entity.ConversationEntity
import com.fusanhe.crm.data.local.entity.CustomerEntity
import com.fusanhe.crm.data.local.entity.MessageEntity

/** List<String> 与 String 的互转 */
class StringListConverter {
    @TypeConverter
    fun fromList(value: List<String>?): String = value?.joinToString("\u0001") ?: ""

    @TypeConverter
    fun toList(value: String?): List<String> =
        if (value.isNullOrBlank()) emptyList() else value.split("\u0001")
}

/**
 * Room 数据库占位定义。
 * 当前阶段未启用（Mock Repository 直接供数）；接入真实后端时作为离线缓存。
 */
@Database(
    entities = [
        CustomerEntity::class,
        ConversationEntity::class,
        MessageEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
@TypeConverters(StringListConverter::class)
abstract class CrmDatabase : RoomDatabase() {
    abstract fun customerDao(): CustomerDao
    abstract fun conversationDao(): ConversationDao
    abstract fun messageDao(): MessageDao
}
