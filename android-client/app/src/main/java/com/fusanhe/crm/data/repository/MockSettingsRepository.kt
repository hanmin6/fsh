package com.fusanhe.crm.data.repository

import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.DemoFlag
import com.fusanhe.crm.domain.model.DemoFlags
import com.fusanhe.crm.domain.model.ThemeMode
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.SettingsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/** 设置仓库 Mock 实现：主题保存在内存，演示开关由 MockModeController 托管 */
@Singleton
class MockSettingsRepository @Inject constructor(
    private val mode: MockModeController,
    private val conversationRepository: ConversationRepository,
) : SettingsRepository {

    private val _themeMode = MutableStateFlow(ThemeMode.LIGHT)
    override val themeMode: Flow<ThemeMode> = _themeMode.asStateFlow()

    override val demoFlags: Flow<DemoFlags> = mode.flags

    override suspend fun setThemeMode(mode: ThemeMode) {
        _themeMode.value = mode
    }

    override suspend fun setDemoFlag(flag: DemoFlag, enabled: Boolean) {
        this.mode.set(flag, enabled)
    }

    override suspend fun clearChatDrafts() {
        conversationRepository.clearAllDrafts()
    }
}
