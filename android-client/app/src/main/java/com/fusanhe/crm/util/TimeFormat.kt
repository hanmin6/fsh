package com.fusanhe.crm.util

import android.text.format.DateUtils
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

object TimeFormat {

    private val dateTimeFormat = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault())
    private val fullDateTimeFormat = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
    private val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())

    fun formatDateTime(timestamp: Long): String = dateTimeFormat.format(Date(timestamp))

    fun formatFullDateTime(timestamp: Long): String = fullDateTimeFormat.format(Date(timestamp))

    fun formatDate(timestamp: Long): String = dateFormat.format(Date(timestamp))

    fun formatRelative(timestamp: Long): String {
        val diff = System.currentTimeMillis() - timestamp
        return when {
            diff < DateUtils.MINUTE_IN_MILLIS -> "刚刚"
            diff < DateUtils.HOUR_IN_MILLIS -> "${diff / DateUtils.MINUTE_IN_MILLIS} 分钟前"
            diff < DateUtils.DAY_IN_MILLIS -> "${diff / DateUtils.HOUR_IN_MILLIS} 小时前"
            diff < 2 * DateUtils.DAY_IN_MILLIS -> "昨天"
            diff < DateUtils.WEEK_IN_MILLIS -> "${diff / DateUtils.DAY_IN_MILLIS} 天前"
            else -> formatDate(timestamp)
        }
    }

    fun formatWaitingMinutes(minutes: Long): String = when {
        minutes < 60 -> "$minutes 分钟"
        minutes < 60 * 24 -> "${minutes / 60} 小时 ${minutes % 60} 分钟"
        else -> "${minutes / (60 * 24)} 天"
    }

    fun formatConfidence(confidence: Float): String =
        "${(confidence * 100).roundToInt().coerceIn(0, 100)}%"
}
