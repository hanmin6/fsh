package com.fusanhe.crm.domain.repository

import com.fusanhe.crm.domain.model.DetectedLanguage
import com.fusanhe.crm.domain.model.Language
import com.fusanhe.crm.domain.model.TranslationResult

interface TranslationRepository {
    suspend fun detectLanguage(text: String): Result<DetectedLanguage>

    /** 翻译客户消息（目标语言：中文） */
    suspend fun translate(text: String, target: Language): Result<TranslationResult>

    /** 翻译业务员回复（目标语言：客户语言） */
    suspend fun translateReply(text: String, target: Language): Result<TranslationResult>
}
