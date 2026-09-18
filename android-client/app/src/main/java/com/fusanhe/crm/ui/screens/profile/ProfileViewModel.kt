package com.fusanhe.crm.ui.screens.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.domain.model.ConversationStatus
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.CustomerRepository
import com.fusanhe.crm.domain.repository.SessionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import java.util.Calendar
import javax.inject.Inject

data class ProfileStats(
    val newCustomersThisMonth: Int,
    val activeInquiries: Int,
)

data class ProfileUiState(
    val userName: String,
    val role: String,
    val department: String,
    val company: String,
    val email: String,
    val stats: ProfileStats = ProfileStats(0, 0),
)

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val sessionRepository: SessionRepository,
    customerRepository: CustomerRepository,
    conversationRepository: ConversationRepository,
) : ViewModel() {

    val state: StateFlow<ProfileUiState> = combine(
        customerRepository.observeCustomers(),
        conversationRepository.observeConversations(),
    ) { customers, conversations ->
        val user = sessionRepository.currentUser
        ProfileUiState(
            userName = user.name,
            role = user.role,
            department = user.department,
            company = user.company,
            email = user.email,
            stats = ProfileStats(
                newCustomersThisMonth = customers.count { it.createdAt >= monthStart() },
                activeInquiries = conversations.count {
                    it.status == ConversationStatus.WAITING_REPLY || it.status == ConversationStatus.WAITING_REVIEW
                },
            ),
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), ProfileUiState(
        userName = sessionRepository.currentUser.name,
        role = sessionRepository.currentUser.role,
        department = sessionRepository.currentUser.department,
        company = sessionRepository.currentUser.company,
        email = sessionRepository.currentUser.email,
    ))

    private val _showLogoutDialog = kotlinx.coroutines.flow.MutableStateFlow(false)
    val showLogoutDialog: StateFlow<Boolean> = _showLogoutDialog.asStateFlow()

    fun showLogoutConfirm() {
        _showLogoutDialog.value = true
    }

    fun dismissLogoutDialog() {
        _showLogoutDialog.value = false
    }

    fun logout() {
        sessionRepository.logout()
    }

    private fun monthStart(): Long = Calendar.getInstance().apply {
        set(Calendar.DAY_OF_MONTH, 1)
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }.timeInMillis
}
