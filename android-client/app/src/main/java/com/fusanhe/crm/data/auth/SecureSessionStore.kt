package com.fusanhe.crm.data.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import com.fusanhe.crm.domain.model.UserProfile
import dagger.hilt.android.qualifiers.ApplicationContext
import java.nio.charset.StandardCharsets
import java.security.KeyStore
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SecureSessionStore @Inject constructor(@ApplicationContext context: Context) {
    private val preferences = context.getSharedPreferences("secure_session", Context.MODE_PRIVATE)

    fun saveUser(user: UserProfile) {
        val fields = listOf(user.id, user.name, user.role, user.department, user.company, user.email)
            .joinToString("\u001f") { Base64.getEncoder().encodeToString(it.toByteArray(StandardCharsets.UTF_8)) }
        preferences.edit().putString(USER, encrypt(fields)).apply()
    }

    fun loadUser(): UserProfile? {
        val encoded = preferences.getString(USER, null) ?: return null
        return runCatching {
            val values = decrypt(encoded).split("\u001f").map {
                String(Base64.getDecoder().decode(it), StandardCharsets.UTF_8)
            }
            require(values.size == 6) { "Invalid encrypted session payload" }
            UserProfile(values[0], values[1], values[2], values[3], values[4], values[5])
        }.getOrNull()
    }

    fun clear() { preferences.edit().clear().apply() }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").run {
            init(KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build())
            generateKey()
        }
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val cipherText = cipher.doFinal(value.toByteArray(StandardCharsets.UTF_8))
        return Base64.getEncoder().encodeToString(cipher.iv) + "." + Base64.getEncoder().encodeToString(cipherText)
    }

    private fun decrypt(value: String): String {
        val (iv, cipherText) = value.split('.', limit = 2)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.getDecoder().decode(iv)))
        return String(cipher.doFinal(Base64.getDecoder().decode(cipherText)), StandardCharsets.UTF_8)
    }

    private companion object {
        const val USER = "user"
        const val ALIAS = "fusanhe-crm-session-v1"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
