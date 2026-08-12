package com.swimanalysis.app.data.local

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import javax.inject.Inject
import javax.inject.Singleton

@Serializable
data class StoredPhoto(
    val uri: String,
    val dateTaken: Long = 0,
    val dateText: String = "",
    val location: String? = null,
    val size: Long = 0
)

private val Context.albumStoreData by preferencesDataStore(name = "album_store")

@Singleton
class AlbumStore @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private val json = Json { ignoreUnknownKeys = true }

    private fun refKey(person: String) = stringPreferencesKey("refs_$person")
    private fun albumKey(person: String) = stringPreferencesKey("album_$person")

    fun referencePaths(person: String): Flow<List<String>> =
        context.albumStoreData.data.map { prefs ->
            val s = prefs[refKey(person)] ?: return@map emptyList()
            runCatching { json.decodeFromString<List<String>>(s) }.getOrDefault(emptyList())
        }

    suspend fun saveReferencePaths(person: String, paths: List<String>) {
        context.albumStoreData.edit { it[refKey(person)] = json.encodeToString(paths) }
    }

    fun albumPhotos(person: String): Flow<List<StoredPhoto>> =
        context.albumStoreData.data.map { prefs ->
            val s = prefs[albumKey(person)] ?: return@map emptyList()
            runCatching { json.decodeFromString<List<StoredPhoto>>(s) }.getOrDefault(emptyList())
        }

    suspend fun saveAlbumPhotos(person: String, photos: List<StoredPhoto>) {
        context.albumStoreData.edit { it[albumKey(person)] = json.encodeToString(photos) }
    }
}