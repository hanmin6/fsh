package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.UserProfile
import kotlinx.coroutines.flow.StateFlow

interface SessionRepository {
    val isLoggedIn: StateFlow<Boolean>
    val currentUser: UserProfile

    /** 演示登录：仅校验格式并模拟延迟，不请求真实后端 */
    suspend fun login(email: String, password: String): Result<UserProfile>

    fun logout()
}
