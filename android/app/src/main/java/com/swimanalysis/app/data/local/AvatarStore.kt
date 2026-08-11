package com.swimanalysis.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.avatarDataStore by preferencesDataStore(name = "avatars")

@Singleton
class AvatarStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private fun keyFor(name: String) = stringPreferencesKey("avatar_$name")

    fun avatarPath(name: String): Flow<String?> =
        context.avatarDataStore.data.map { prefs -> prefs[keyFor(name)] }

    suspend fun saveAvatarPath(name: String, path: String) {
        context.avatarDataStore.edit { prefs -> prefs[keyFor(name)] = path }
    }
}