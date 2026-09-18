package com.fusanhe.crm.ui.screens.chat

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fusanhe.crm.data.mock.MockModeController
import com.fusanhe.crm.domain.model.AIReplySuggestion
import com.fusanhe.crm.domain.model.Attachment
import com.fusanhe.crm.domain.model.Conversation
import com.fusanhe.crm.domain.model.Language
import com.fusanhe.crm.domain.model.Message
import com.fusanhe.crm.domain.model.MessageDisplayMode
import com.fusanhe.crm.domain.repository.AIReplyRepository
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.TranslationRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/** AI 建议弹层状态 */
sealed interface AiSuggestionSheetState {
    data object Hidden : AiSuggestionSheetState
    data object Generating : AiSuggestionSheetState
    data class Ready(val suggestion: AIReplySuggestion) : AiSuggestionSheetState
    data class Failed(val message: String) : AiSuggestionSheetState
}

/** 翻译编辑弹层状态 */
sealed interface TranslateSheetState {
    data object Hidden : TranslateSheetState

    data class Loading(
        val sourceText: String,
        val targetLanguage: Language,
        /** true = 翻译"我的草稿"，采用时填入译文；false = 编辑 AI 建议，采用时填入原文 */
        val translatingReply: Boolean,
    ) : TranslateSheetState

    data class Result(
        val originalText: String,
        val translatedText: String,
        val sourceLanguage: Language,
        val targetLanguage: Language,
        val translatingReply: Boolean,
        val swapped: Boolean = false,
    ) : TranslateSheetState

    data class Failed(
        val sourceText: String,
        val targetLanguage: Language,
        val message: String,
        val translatingReply: Boolean,
    ) : TranslateSheetState
}

data class ChatUiState(
    val conversation: Conversation? = null,
    val messages: List<Message> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
    val draft: String = "",
    val displayMode: MessageDisplayMode = MessageDisplayMode.ORIGINAL_WITH_TRANSLATION,
    val sending: Boolean = false,
    val attachments: List<Attachment> = emptyList(),
    val aiSheetVisible: Boolean = false,
    val aiState: AiSuggestionSheetState = AiSuggestionSheetState.Hidden,
    val translateSheet: TranslateSheetState = TranslateSheetState.Hidden,
    val phrasesSheetVisible: Boolean = false,
    /** 演示：手动触发的单条消息翻译（messageId -> 中文译文） */
    val messageTranslations: Map<String, String> = emptyMap(),
    val translatingMessageIds: Set<String> = emptySet(),
    val messageTranslationErrors: Map<String, String> = emptyMap(),
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val conversationRepository: ConversationRepository,
    private val aiReplyRepository: AIReplyRepository,
    private val translationRepository: TranslationRepository,
    private val mode: MockModeController,
) : ViewModel() {

    val conversationId: String = checkNotNull(savedStateHandle["conversationId"])

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private val _events = MutableSharedFlow<String>(extraBufferCapacity = 8)
    val events: SharedFlow<String> = _events.asSharedFlow()

    private var knownMessageIds: Set<String> = emptySet()
    private var firstMessagesLoad = true

    init {
        viewModelScope.launch {
            conversationRepository.getConversation(conversationId)
                .onSuccess { conversation ->
                    _state.update { it.copy(conversation = conversation) }
                }
                .onFailure { e ->
                    _state.update { it.copy(loading = false, error = e.message ?: "会话加载失败") }
                }
        }

        viewModelScope.launch {
            conversationRepository.observeMessages(conversationId).collectLatest { messages ->
                val newIncoming = messages.filter {
                    it.direction == com.fusanhe.crm.domain.model.MessageDirection.INCOMING &&
                        it.id !in knownMessageIds
                }
                val isFirst = firstMessagesLoad
                firstMessagesLoad = false
                knownMessageIds = messages.map { it.id }.toSet()
                _state.update { it.copy(messages = messages, loading = false) }
                conversationRepository.markAsRead(conversationId)
                if (!isFirst && newIncoming.isNotEmpty()) {
                    _events.emit("收到来自 ${newIncoming.first().senderName} 的新消息")
                }
            }
        }

        viewModelScope.launch {
            conversationRepository.observeDraft(conversationId).collect { draft ->
                _state.update { if (it.draft != draft) it.copy(draft = draft) else it }
            }
        }
    }

    // ---- 输入与草稿 ----

    fun onDraftChange(text: String) {
        _state.update { it.copy(draft = text) }
        viewModelScope.launch { conversationRepository.saveLocalDraft(conversationId, text) }
    }

    fun toggleDisplayMode() {
        _state.update {
            it.copy(
                displayMode = if (it.displayMode == MessageDisplayMode.ORIGINAL_ONLY) {
                    MessageDisplayMode.ORIGINAL_WITH_TRANSLATION
                } else {
                    MessageDisplayMode.ORIGINAL_ONLY
                }
            )
        }
    }

    // ---- 发送（演示） ----

    fun sendMessage() {
        val current = _state.value
        val text = current.draft.trim()
        if (text.isEmpty() || current.sending) return
        viewModelScope.launch {
            _events.emit("演示模式：消息不会发送到真实平台")
            _state.update { it.copy(sending = true, draft = "", attachments = emptyList()) }
            conversationRepository.saveLocalDraft(conversationId, "")
            conversationRepository.sendMockMessage(conversationId, text, current.attachments)
                .onSuccess {
                    _state.update { it.copy(sending = false) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(sending = false, draft = text, attachments = current.attachments)
                    }
                    _events.emit(e.message ?: "发送失败，请重试")
                }
        }
    }

    // ---- 附件（占位） ----

    fun addAttachment(attachment: Attachment) {
        _state.update { it.copy(attachments = it.attachments + attachment) }
    }

    fun removeAttachment(attachmentId: String) {
        _state.update { it.copy(attachments = it.attachments.filterNot { a -> a.id == attachmentId }) }
    }

    // ---- 常用语 ----

    fun showPhrasesSheet() = _state.update { it.copy(phrasesSheetVisible = true) }

    fun hidePhrasesSheet() = _state.update { it.copy(phrasesSheetVisible = false) }

    fun usePhrase(text: String) {
        val current = _state.value.draft
        val merged = if (current.isBlank()) text else "$current\n$text"
        onDraftChange(merged)
        hidePhrasesSheet()
    }

    // ---- 消息区单条翻译 ----

    fun translateMessage(message: Message) {
        if (message.id in _state.value.translatingMessageIds) return
        viewModelScope.launch {
            _state.update { it.copy(translatingMessageIds = it.translatingMessageIds + message.id) }
            translationRepository.translate(message.originalText, Language.CHINESE)
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            messageTranslations = it.messageTranslations + (message.id to result.translatedText),
                            translatingMessageIds = it.translatingMessageIds - message.id,
                            messageTranslationErrors = it.messageTranslationErrors - message.id,
                        )
                    }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(
                            translatingMessageIds = it.translatingMessageIds - message.id,
                            messageTranslationErrors = it.messageTranslationErrors +
                                (message.id to (e.message ?: "翻译失败")),
                        )
                    }
                }
        }
    }

    // ---- 翻译编辑弹层 ----

    /** 翻译底部输入框中的中文草稿为客户语言 */
    fun openDraftTranslateSheet() {
        val current = _state.value
        val text = current.draft.trim()
        if (text.isEmpty()) {
            viewModelScope.launch { _events.emit("请先在输入框输入要翻译的内容") }
            return
        }
        val target = Language.fromCode(current.conversation?.language)
        _state.update { it.copy(translateSheet = TranslateSheetState.Loading(text, target, translatingReply = true)) }
        viewModelScope.launch {
            translationRepository.translateReply(text, target)
                .onSuccess { result ->
                    _state.update {
                        it.copy(
                            translateSheet = TranslateSheetState.Result(
                                originalText = text,
                                translatedText = result.translatedText,
                                sourceLanguage = result.sourceLanguage,
                                targetLanguage = target,
                                translatingReply = true,
                            )
                        )
                    }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(
                            translateSheet = TranslateSheetState.Failed(
                                text, target, e.message ?: "翻译失败", translatingReply = true,
                            )
                        )
                    }
                }
        }
    }

    /** 编辑 AI 建议（原文为 AI 草稿，译文为中文对照） */
    fun openSuggestionEditSheet(suggestion: AIReplySuggestion) {
        _state.update {
            it.copy(
                aiSheetVisible = false,
                translateSheet = TranslateSheetState.Result(
                    originalText = suggestion.draftText,
                    translatedText = suggestion.translatedText,
                    sourceLanguage = Language.fromCode(suggestion.suggestedLanguage),
                    targetLanguage = Language.CHINESE,
                    translatingReply = false,
                ),
            )
        }
    }

    fun onSheetOriginalChange(text: String) {
        _state.update {
            val sheet = it.translateSheet
            if (sheet is TranslateSheetState.Result) {
                it.copy(translateSheet = sheet.copy(originalText = text))
            } else {
                it
            }
        }
    }

    fun onSheetTranslatedChange(text: String) {
        _state.update {
            val sheet = it.translateSheet
            if (sheet is TranslateSheetState.Result) {
                it.copy(translateSheet = sheet.copy(translatedText = text))
            } else {
                it
            }
        }
    }

    /** 交换原文/译文的展示位置 */
    fun swapSheetDisplay() {
        _state.update {
            val sheet = it.translateSheet
            if (sheet is TranslateSheetState.Result) {
                it.copy(translateSheet = sheet.copy(swapped = !sheet.swapped))
            } else {
                it
            }
        }
    }

    fun retrySheetTranslation() {
        when (val sheet = _state.value.translateSheet) {
            is TranslateSheetState.Failed -> {
                if (sheet.translatingReply) {
                    _state.update {
                        it.copy(translateSheet = TranslateSheetState.Loading(sheet.sourceText, sheet.targetLanguage, true))
                    }
                    viewModelScope.launch {
                        translationRepository.translateReply(sheet.sourceText, sheet.targetLanguage)
                            .onSuccess { result ->
                                _state.update {
                                    it.copy(
                                        translateSheet = TranslateSheetState.Result(
                                            sheet.sourceText, result.translatedText,
                                            result.sourceLanguage, sheet.targetLanguage, true,
                                        )
                                    )
                                }
                            }
                            .onFailure { e ->
                                _state.update {
                                    it.copy(
                                        translateSheet = TranslateSheetState.Failed(
                                            sheet.sourceText, sheet.targetLanguage,
                                            e.message ?: "翻译失败", true,
                                        )
                                    )
                                }
                            }
                    }
                }
            }
            else -> Unit
        }
    }

    /** 采用译文/原文填入输入框（不自动发送） */
    fun adoptSheetText() {
        val sheet = _state.value.translateSheet
        if (sheet is TranslateSheetState.Result) {
            val text = if (sheet.translatingReply) sheet.translatedText else sheet.originalText
            onDraftChange(text)
            _state.update { it.copy(translateSheet = TranslateSheetState.Hidden) }
            viewModelScope.launch {
                _events.emit("已填入输入框，请检查后手动发送")
            }
        }
    }

    fun closeTranslateSheet() {
        _state.update { it.copy(translateSheet = TranslateSheetState.Hidden) }
    }

    // ---- AI 建议 ----

    fun openAiSheet() {
        val current = _state.value.aiState
        _state.update { it.copy(aiSheetVisible = true) }
        if (current is AiSuggestionSheetState.Ready) return // 已有建议直接展示
        generateSuggestion(regenerate = false)
    }

    fun generateSuggestion(regenerate: Boolean) {
        if (_state.value.aiState is AiSuggestionSheetState.Generating) return
        _state.update { it.copy(aiSheetVisible = true, aiState = AiSuggestionSheetState.Generating) }
        viewModelScope.launch {
            val result = if (regenerate) {
                aiReplyRepository.regenerateSuggestion(conversationId)
            } else {
                aiReplyRepository.generateSuggestion(conversationId)
            }
            result
                .onSuccess { suggestion ->
                    _state.update { it.copy(aiState = AiSuggestionSheetState.Ready(suggestion)) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(aiState = AiSuggestionSheetState.Failed(e.message ?: "AI 生成失败"))
                    }
                }
        }
    }

    /** 采用建议：仅填入输入框，不自动发送 */
    fun adoptSuggestion() {
        val ai = _state.value.aiState
        if (ai is AiSuggestionSheetState.Ready) {
            viewModelScope.launch {
                aiReplyRepository.acceptSuggestion(ai.suggestion.id)
                onDraftChange(ai.suggestion.draftText)
                _state.update { it.copy(aiSheetVisible = false) }
                _events.emit("已采用 AI 建议，请检查后手动发送")
            }
        }
    }

    fun closeAiSheet() {
        _state.update { it.copy(aiSheetVisible = false) }
    }

    // ---- 演示控制 ----

    /** 模拟客户发来新消息 */
    fun simulateIncomingMessage() {
        viewModelScope.launch {
            conversationRepository.simulateIncomingMessage(conversationId)
        }
    }
}
