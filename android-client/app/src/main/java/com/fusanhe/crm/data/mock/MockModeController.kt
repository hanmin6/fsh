package com.fusanhe.crm.data.mock

import com.fusanhe.crm.domain.model.DemoFlag
import com.fusanhe.crm.domain.model.DemoFlags
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 演示模式控制器：设置页可随时打开各类"失败/离线"模拟开关，
 * 各 Mock Repository 读取这里的标志来模拟对应异常场景。
 */
@Singleton
class MockModeController @Inject constructor() {

    private val _flags = MutableStateFlow(DemoFlags())
    val flags: StateFlow<DemoFlags> = _flags.asStateFlow()

    fun set(flag: DemoFlag, enabled: Boolean) {
        _flags.update { current ->
            when (flag) {
                DemoFlag.NETWORK_FAILURE -> current.copy(networkFailure = enabled)
                DemoFlag.TRANSLATION_FAILURE -> current.copy(translationFailure = enabled)
                DemoFlag.SEND_FAILURE -> current.copy(sendFailure = enabled)
                DemoFlag.SAVE_FAILURE -> current.copy(saveCustomerFailure = enabled)
                DemoFlag.OFFLINE -> current.copy(offline = enabled)
            }
        }
    }

    fun reset() {
        _flags.value = DemoFlags()
    }
}
