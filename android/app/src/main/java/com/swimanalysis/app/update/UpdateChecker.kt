package com.swimanalysis.app.update

import com.swimanalysis.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.net.HttpURLConnection
import java.net.URL
import javax.inject.Inject
import javax.inject.Singleton

data class UpdateInfo(
    val latestVersion: String,
    val latestVersionCode: Int,
    val downloadUrl: String,
    val fileSize: Long,
    val releaseNotes: String,
    val hasUpdate: Boolean
)

@Singleton
class UpdateChecker @Inject constructor() {

    companion object {
        private const val OWNER = "yangopenclaw-gif"
        private const val REPO = "Swim_Video_Analysis"
        private const val API_URL = "https://api.github.com/repos/$OWNER/$REPO/releases/latest"
        private const val TAG_API_URL = "https://api.github.com/repos/$OWNER/$REPO/releases/tags"
    }

    suspend fun getAssetDownloadUrl(versionName: String): String = withContext(Dispatchers.IO) {
        val json = Json { ignoreUnknownKeys = true }
        val tag = "v$versionName"
        try {
            val conn = (URL("$TAG_API_URL/$tag").openConnection() as HttpURLConnection).apply {
                connectTimeout = 10000
                readTimeout = 15000
                setRequestProperty("Accept", "application/vnd.github+json")
            }
            try {
                if (conn.responseCode != 200) return@withContext ""
                val body = conn.inputStream.bufferedReader().use { it.readText() }
                val release = json.parseToJsonElement(body).jsonObject
                val assets = release["assets"]?.jsonArray ?: JsonArray(emptyList())

                for (asset in assets) {
                    val obj = asset.jsonObject
                    val name = obj["name"]?.jsonPrimitive?.contentOrNull ?: ""
                    if (name.endsWith(".apk") && name.contains("debug")) {
                        return@withContext obj["browser_download_url"]?.jsonPrimitive?.contentOrNull ?: ""
                    }
                }

                for (asset in assets) {
                    val obj = asset.jsonObject
                    val name = obj["name"]?.jsonPrimitive?.contentOrNull ?: ""
                    if (name.endsWith(".apk")) {
                        return@withContext obj["browser_download_url"]?.jsonPrimitive?.contentOrNull ?: ""
                    }
                }
                ""
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            ""
        }
    }

    suspend fun checkForUpdate(): UpdateInfo = withContext(Dispatchers.IO) {
        val json = Json { ignoreUnknownKeys = true }

        val conn = (URL(API_URL).openConnection() as HttpURLConnection).apply {
            connectTimeout = 10000
            readTimeout = 15000
            setRequestProperty("Accept", "application/vnd.github+json")
        }

        try {
            val responseCode = conn.responseCode
            if (responseCode != 200) {
                throw Exception("GitHub API返回 $responseCode")
            }

            val body = conn.inputStream.bufferedReader().use { it.readText() }
            val release = json.parseToJsonElement(body).jsonObject

            val tagName = release["tag_name"]?.jsonPrimitive?.contentOrNull ?: ""
            val releaseName = release["name"]?.jsonPrimitive?.contentOrNull ?: tagName
            val body2 = release["body"]?.jsonPrimitive?.contentOrNull ?: ""

            val versionName = tagName.removePrefix("v")
            val versionCode = parseVersionCode(versionName)

            val assets = release["assets"]?.jsonArray ?: JsonArray(emptyList())
            var downloadUrl = ""
            var fileSize = 0L

            for (asset in assets) {
                val obj = asset.jsonObject
                val name = obj["name"]?.jsonPrimitive?.contentOrNull ?: ""
                if (name.endsWith(".apk") && name.contains("debug")) {
                    downloadUrl = obj["browser_download_url"]?.jsonPrimitive?.contentOrNull ?: ""
                    fileSize = obj["size"]?.jsonPrimitive?.contentOrNull?.toLongOrNull() ?: 0L
                    break
                }
            }

            if (downloadUrl.isEmpty() && assets.isNotEmpty()) {
                val obj = assets[0].jsonObject
                downloadUrl = obj["browser_download_url"]?.jsonPrimitive?.contentOrNull ?: ""
                fileSize = obj["size"]?.jsonPrimitive?.contentOrNull?.toLongOrNull() ?: 0L
            }

            val hasUpdate = versionCode > BuildConfig.VERSION_CODE

            UpdateInfo(
                latestVersion = versionName,
                latestVersionCode = versionCode,
                downloadUrl = downloadUrl,
                fileSize = fileSize,
                releaseNotes = body2.ifEmpty { releaseName },
                hasUpdate = hasUpdate
            )
        } finally {
            conn.disconnect()
        }
    }

    private fun parseVersionCode(versionName: String): Int {
        val parts = versionName.split(".")
        return try {
            val major = parts.getOrNull(0)?.toIntOrNull() ?: 0
            val minor = parts.getOrNull(1)?.toIntOrNull() ?: 0
            val patch = parts.getOrNull(2)?.toIntOrNull() ?: 0
            major * 10000 + minor * 100 + patch
        } catch (e: Exception) {
            0
        }
    }
}