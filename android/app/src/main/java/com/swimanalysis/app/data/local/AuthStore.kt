package com.swimanalysis.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

private val Context.authDataStore by preferencesDataStore(name = "auth_store")

@Singleton
class AuthStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val KEY_TOKEN = stringPreferencesKey("token")
    private val KEY_USERNAME = stringPreferencesKey("username")

    @Volatile
    private var cachedToken: String? = null

    private val _isLoggedIn = MutableStateFlow<Boolean?>(null)
    val isLoggedIn: StateFlow<Boolean?> = _isLoggedIn.asStateFlow()

    private val _username = MutableStateFlow<String?>(null)
    val username: StateFlow<String?> = _username.asStateFlow()

    private val _locked = MutableStateFlow(false)
    val locked: StateFlow<Boolean> = _locked.asStateFlow()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    init {
        scope.launch {
            val prefs = context.authDataStore.data.first()
            cachedToken = prefs[KEY_TOKEN]
            _username.value = prefs[KEY_USERNAME]
            _isLoggedIn.value = cachedToken != null
            _locked.value = cachedToken != null
        }
    }

    fun currentToken(): String? = cachedToken

    fun lock() {
        _locked.value = true
    }

    fun unlock() {
        _locked.value = false
    }

    suspend fun save(token: String, name: String) {
        context.authDataStore.edit {
            it[KEY_TOKEN] = token
            it[KEY_USERNAME] = name
        }
        cachedToken = token
        _username.value = name
        _isLoggedIn.value = true
        _locked.value = false
    }

    suspend fun clear() {
        context.authDataStore.edit {
            it.remove(KEY_TOKEN)
            it.remove(KEY_USERNAME)
        }
        cachedToken = null
        _username.value = null
        _isLoggedIn.value = false
        _locked.value = false
    }
}