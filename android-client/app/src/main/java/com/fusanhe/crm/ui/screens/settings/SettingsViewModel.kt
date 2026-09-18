package com.fusanhe.crm.ui.screens.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.DemoFlag
import com.fusanhe.crm.domain.model.DemoFlags
import com.fusanhe.crm.domain.model.ThemeMode
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsRepository: SettingsRepository,
    private val conversationRepository: ConversationRepository,
) : ViewModel() {

    val themeMode: StateFlow<ThemeMode> =
        settingsRepository.themeMode.stateIn(viewModelScope, SharingStarted.Eagerly, ThemeMode.LIGHT)

    val demoFlags: StateFlow<DemoFlags> =
        settingsRepository.demoFlags.stateIn(viewModelScope, SharingStarted.Eagerly, DemoFlags())

    fun setThemeMode(mode: ThemeMode) {
        viewModelScope.launch { settingsRepository.setThemeMode(mode) }
    }

    fun setDemoFlag(flag: DemoFlag, enabled: Boolean) {
        viewModelScope.launch { settingsRepository.setDemoFlag(flag, enabled) }
    }

    fun clearChatDrafts(onCleared: () -> Unit) {
        viewModelScope.launch {
            settingsRepository.clearChatDrafts()
            onCleared()
        }
    }

    /** 演示：在第一个未结束的会话中模拟一条客户消息 */
    fun simulateIncoming(onDone: (String?) -> Unit) {
        viewModelScope.launch {
            val target = conversationRepository.observeConversations().first()
                .firstOrNull { it.status != com.fusanhe.crm.domain.model.ConversationStatus.CLOSED }
            if (target != null) {
                conversationRepository.simulateIncomingMessage(target.id)
                onDone(target.customerName)
            } else {
                onDone(null)
            }
        }
    }
}
