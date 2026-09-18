package com.fusanhe.crm.di

import com.fusanhe.crm.data.repository.MockAIReplyRepository
import com.fusanhe.crm.data.repository.MockConversationRepository
import com.fusanhe.crm.data.repository.MockCustomerRepository
import com.fusanhe.crm.data.repository.MockNotificationRepository
import com.fusanhe.crm.data.repository.MockSessionRepository
import com.fusanhe.crm.data.repository.MockSettingsRepository
import com.fusanhe.crm.data.repository.MockTranslationRepository
import com.fusanhe.crm.domain.repository.AIReplyRepository
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.CustomerRepository
import com.fusanhe.crm.domain.repository.NotificationRepository
import com.fusanhe.crm.domain.repository.SessionRepository
import com.fusanhe.crm.domain.repository.SettingsRepository
import com.fusanhe.crm.domain.repository.TranslationRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * 仓库绑定：当前全部指向 Mock 实现。
 * 接入真实后端时，把 @Binds 的目标替换为 RemoteXxxRepository 即可，UI 层零改动。
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class DataModule {

    @Binds
    @Singleton
    abstract fun bindCustomerRepository(impl: MockCustomerRepository): CustomerRepository

    @Binds
    @Singleton
    abstract fun bindConversationRepository(impl: MockConversationRepository): ConversationRepository

    @Binds
    @Singleton
    abstract fun bindAIReplyRepository(impl: MockAIReplyRepository): AIReplyRepository

    @Binds
    @Singleton
    abstract fun bindTranslationRepository(impl: MockTranslationRepository): TranslationRepository

    @Binds
    @Singleton
    abstract fun bindSettingsRepository(impl: MockSettingsRepository): SettingsRepository

    @Binds
    @Singleton
    abstract fun bindSessionRepository(impl: MockSessionRepository): SessionRepository

    @Binds
    @Singleton
    abstract fun bindNotificationRepository(impl: MockNotificationRepository): NotificationRepository
}
