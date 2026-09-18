package com.fusanhe.crm.data.mock

private const val MINUTE = 60_000L
private const val HOUR = 3_600_000L
private const val DAY = 86_400_000L

/** Mock 数据统一使用"相对当前时间"的时间戳，保证演示时数据始终新鲜 */
internal fun now(): Long = System.currentTimeMillis()

internal fun minutesAgo(m: Long): Long = now() - m * MINUTE

internal fun hoursAgo(h: Long): Long = now() - h * HOUR

internal fun daysAgo(d: Long): Long = now() - d * DAY
