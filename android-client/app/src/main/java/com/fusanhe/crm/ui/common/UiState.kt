package com.fusanhe.crm.ui.common

/**
 * 页面通用 UiState：加载 / 内容 / 空数据 / 错误。
 * 每个主要页面均使用独立 UiState，避免共享可变状态。
 */
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Content<T>(val data: T) : UiState<T>
    data object Empty : UiState<Nothing>
    data class Error(val message: String) : UiState<Nothing>
}
