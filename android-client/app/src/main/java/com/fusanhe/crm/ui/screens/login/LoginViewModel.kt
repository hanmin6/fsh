package com.fusanhe.crm.ui.screens.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.domain.repository.SessionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val emailError: String? = null,
    val passwordError: String? = null,
    val loading: Boolean = false,
    val errorMessage: String? = null,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val sessionRepository: SessionRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun onEmailChange(value: String) = _state.update { it.copy(email = value, emailError = null) }

    fun onPasswordChange(value: String) =
        _state.update { it.copy(password = value, passwordError = null) }

    fun login(onSuccess: () -> Unit) {
        val current = _state.value
        var hasError = false
        var emailError: String? = null
        var passwordError: String? = null
        if (current.email.isBlank()) {
            emailError = "请输入邮箱"; hasError = true
        } else if (!current.email.contains('@')) {
            emailError = "邮箱格式不正确"; hasError = true
        }
        if (current.password.isBlank()) {
            passwordError = "请输入密码"; hasError = true
        }
        if (hasError) {
            _state.update { it.copy(emailError = emailError, passwordError = passwordError) }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(loading = true, errorMessage = null) }
            sessionRepository.login(current.email, current.password)
                .onSuccess {
                    _state.update { s -> s.copy(loading = false) }
                    onSuccess()
                }
                .onFailure { e ->
                    _state.update { s ->
                        s.copy(loading = false, errorMessage = e.message ?: "登录失败，请重试")
                    }
                }
        }
    }
}
