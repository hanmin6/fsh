package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.auth.AuthSession
import com.fusanhe.crm.data.auth.SecureSessionStore
import com.fusanhe.crm.data.remote.api.CrmApiService
import com.fusanhe.crm.domain.model.UserProfile
import com.fusanhe.crm.domain.repository.SessionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import com.fusanhe.crm.di.ApplicationScope
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RemoteSessionRepository @Inject constructor(
    private val api: CrmApiService,
    private val authSession: AuthSession,
    private val store: SecureSessionStore,
    @ApplicationScope appScope: CoroutineScope,
) : SessionRepository {
    private val emptyUser = UserProfile("", "", "", "", "福三和食品有限公司", "")
    private var user = store.loadUser() ?: emptyUser
    private val loggedIn = MutableStateFlow(false) // Basic secret is deliberately not restored from disk.
    override val isLoggedIn: StateFlow<Boolean> = loggedIn.asStateFlow()
    override val currentUser: UserProfile get() = user

    init {
        appScope.launch {
            authSession.active.collectLatest { active ->
                if (!active) {
                    store.clear()
                    loggedIn.value = false
                }
            }
        }
    }

    override suspend fun login(email: String, password: String): Result<UserProfile> = runCatching {
        require(email.isNotBlank() && password.isNotBlank()) { "请输入账号和密码" }
        authSession.beginBasic(email.trim(), password)
        val remote = api.getCurrentUser()
        UserProfile(
            id = remote.id,
            name = remote.name.ifBlank { remote.userName ?: email.trim() },
            role = remote.type ?: "用户",
            department = remote.teamNames.values.firstOrNull().orEmpty(),
            company = "福三和食品有限公司",
            email = remote.emailAddress ?: email.trim(),
        ).also {
            user = it
            store.saveUser(it)
            loggedIn.value = true
        }
    }.onFailure {
        authSession.clear()
        loggedIn.value = false
    }

    override fun logout() {
        authSession.clear()
        store.clear()
        user = emptyUser
        loggedIn.value = false
    }
}
