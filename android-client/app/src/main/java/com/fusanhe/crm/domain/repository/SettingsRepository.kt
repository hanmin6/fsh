package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.DemoFlag
import com.fusanhe.crm.domain.model.DemoFlags
import com.fusanhe.crm.domain.model.ThemeMode
import kotlinx.coroutines.flow.Flow

interface SettingsRepository {
    val themeMode: Flow<ThemeMode>
    suspend fun setThemeMode(mode: ThemeMode)

    val demoFlags: Flow<DemoFlags>
    suspend fun setDemoFlag(flag: DemoFlag, enabled: Boolean)

    suspend fun clearChatDrafts()
}
