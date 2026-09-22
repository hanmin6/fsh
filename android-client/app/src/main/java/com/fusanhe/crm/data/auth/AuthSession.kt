package com.fusanhe.crm.data.auth

import java.nio.charset.StandardCharsets
import java.util.Base64
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** Runtime-only Basic credential. Passwords are never handed to persistent storage. */
@Singleton
class AuthSession @Inject constructor() {
    @Volatile private var authorization: String? = null
    private val _active = MutableStateFlow(false)
    val active: StateFlow<Boolean> = _active.asStateFlow()

    fun beginBasic(userName: String, password: String) {
        val encoded = Base64.getEncoder().encodeToString("$userName:$password".toByteArray(StandardCharsets.UTF_8))
        authorization = encoded
        _active.value = true
    }

    fun authorizationHeader(): String? = authorization
    fun clear() {
        authorization = null
        _active.value = false
    }
}
