package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockData
import com.fusanhe.crm.domain.model.UserProfile
import com.fusanhe.crm.domain.repository.SessionRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** 登录会话 Mock 实现：仅做格式校验与延迟模拟，不请求真实后端 */
@Singleton
class MockSessionRepository @Inject constructor() : SessionRepository {

    private val _isLoggedIn = MutableStateFlow(false)
    override val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()

    override val currentUser: UserProfile get() = MockData.currentUser

    override suspend fun login(email: String, password: String): Result<UserProfile> {
        delay(800)
        val mail = email.trim()
        if (!mail.contains('@') || mail.length < 5) {
            return Result.failure(IllegalArgumentException("请输入有效的邮箱地址"))
        }
        if (password.isBlank()) {
            return Result.failure(IllegalArgumentException("请输入密码"))
        }
        _isLoggedIn.value = true
        return Result.success(currentUser)
    }

    override fun logout() {
        _isLoggedIn.value = false
    }
}
