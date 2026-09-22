package com.fusanhe.crm.data.auth

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Base64

class SessionStoreTest {
    @Test fun runtime_auth_is_cleared_on_logout() {
        val session = AuthSession()
        session.beginBasic("user@example.com", "never-persist-this")
        assertTrue(session.authorizationHeader()?.isNotBlank() == true)
        session.clear()
        assertNull(session.authorizationHeader())
        assertFalse(session.active.value)
    }

    @Test fun header_is_encoded_and_not_plaintext() {
        val session = AuthSession()
        session.beginBasic("user", "secret")
        val header = session.authorizationHeader().orEmpty()
        assertFalse(header.contains("secret"))
        assertTrue(String(Base64.getDecoder().decode(header)).endsWith(":secret"))
        assertTrue(session.active.value)
    }
}
