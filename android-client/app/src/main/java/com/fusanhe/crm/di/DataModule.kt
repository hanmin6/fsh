package com.fusanhe.crm.di

import com.fusanhe.crm.BuildConfig
import com.fusanhe.crm.data.repository.MockAIReplyRepository
import com.fusanhe.crm.data.repository.MockConversationRepository
import com.fusanhe.crm.data.repository.MockCustomerRepository
import com.fusanhe.crm.data.repository.MockNotificationRepository
import com.fusanhe.crm.data.repository.MockSessionRepository
import com.fusanhe.crm.data.repository.MockSettingsRepository
import com.fusanhe.crm.data.repository.MockTranslationRepository
import com.fusanhe.crm.data.repository.RemoteAIReplyRepository
import com.fusanhe.crm.data.repository.RemoteConversationRepository
import com.fusanhe.crm.data.repository.RemoteCustomerRepository
import com.fusanhe.crm.data.repository.RemoteSessionRepository
import com.fusanhe.crm.domain.repository.AIReplyRepository
import com.fusanhe.crm.domain.repository.ConversationRepository
import com.fusanhe.crm.domain.repository.CustomerRepository
import com.fusanhe.crm.domain.repository.NotificationRepository
import com.fusanhe.crm.domain.repository.SessionRepository
import com.fusanhe.crm.domain.repository.SettingsRepository
import com.fusanhe.crm.domain.repository.TranslationRepository
import dagger.Module
import dagger.Provides
import dagger.Lazy
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/** One explicit build flag selects the complete mock or production data foundation. */
@Module
@InstallIn(SingletonComponent::class)
object DataModule {
    @Provides @Singleton
    fun customer(mock: Lazy<MockCustomerRepository>, remote: Lazy<RemoteCustomerRepository>): CustomerRepository =
        if (BuildConfig.FUSANHE_USE_REMOTE) remote.get() else mock.get()

    @Provides @Singleton
    fun conversation(mock: Lazy<MockConversationRepository>, remote: Lazy<RemoteConversationRepository>): ConversationRepository =
        if (BuildConfig.FUSANHE_USE_REMOTE) remote.get() else mock.get()

    @Provides @Singleton
    fun aiReply(mock: Lazy<MockAIReplyRepository>, remote: Lazy<RemoteAIReplyRepository>): AIReplyRepository =
        if (BuildConfig.FUSANHE_USE_REMOTE) remote.get() else mock.get()

    @Provides @Singleton
    fun session(mock: Lazy<MockSessionRepository>, remote: Lazy<RemoteSessionRepository>): SessionRepository =
        if (BuildConfig.FUSANHE_USE_REMOTE) remote.get() else mock.get()

    @Provides @Singleton fun translation(impl: MockTranslationRepository): TranslationRepository = impl
    @Provides @Singleton fun settings(impl: MockSettingsRepository): SettingsRepository = impl
    @Provides @Singleton fun notifications(impl: MockNotificationRepository): NotificationRepository = impl
}
