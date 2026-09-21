package com.fusanhe.crm.di

import android.content.Context
import androidx.room.Room
import com.fusanhe.crm.BuildConfig
import com.fusanhe.crm.data.auth.AuthSession
import com.fusanhe.crm.data.local.CrmDatabase
import com.fusanhe.crm.data.remote.api.CrmApiService
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Qualifier
import javax.inject.Singleton

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class ApiBaseUrl

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    @ApplicationScope
    fun provideApplicationScope(): CoroutineScope =
        CoroutineScope(SupervisorJob() + Dispatchers.Default)
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): CrmDatabase =
        Room.databaseBuilder(context, CrmDatabase::class.java, "fusanhe_crm.db")
            .build()
}

/**
 * Network layer with explicit build-time endpoint and runtime-only auth.
 */
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    @ApiBaseUrl
    fun provideApiBaseUrl(): String = BuildConfig.FUSANHE_API_BASE_URL

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(authSession: AuthSession): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor { chain ->
            val request = chain.request().newBuilder()
                .header("X-Request-Id", java.util.UUID.randomUUID().toString())
            authSession.authorizationHeader()?.let { request.header("X-Espo-Authorization", it) }
            chain.proceed(request.build()).also { response ->
                if (response.code == 401) authSession.clear()
            }
        }
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    @Provides
    @Singleton
    fun provideRetrofit(
        @ApiBaseUrl baseUrl: String,
        okHttpClient: OkHttpClient,
        json: Json,
    ): Retrofit = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    @Provides
    @Singleton
    fun provideCrmApiService(retrofit: Retrofit): CrmApiService =
        retrofit.create(CrmApiService::class.java)
}
