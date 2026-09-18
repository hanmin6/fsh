package com.fusanhe.crm.di

import javax.inject.Qualifier

/** 应用级协程作用域（Mock 数据的定时模拟等后台任务使用） */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class ApplicationScope
