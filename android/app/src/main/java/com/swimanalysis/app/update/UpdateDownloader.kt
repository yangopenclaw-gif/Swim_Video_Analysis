package com.swimanalysis.app.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import javax.inject.Inject
import javax.inject.Singleton

data class DownloadState(
    val progress: Float = 0f,
    val downloadedBytes: Long = 0L,
    val totalBytes: Long = 0L,
    val status: DownloadStatus = DownloadStatus.IDLE,
    val filePath: String = ""
)

enum class DownloadStatus { IDLE, DOWNLOADING, COMPLETED, FAILED }

@Singleton
class UpdateDownloader @Inject constructor() {

    fun download(context: Context, url: String, fileName: String = "swim-analysis-update.apk"): Flow<DownloadState> = flow {
        var state = DownloadState(status = DownloadStatus.DOWNLOADING)
        emit(state)

        try {
            val updateDir = File(context.cacheDir, "updates")
            if (!updateDir.exists()) updateDir.mkdirs()
            val targetFile = File(updateDir, fileName)
            if (targetFile.exists()) targetFile.delete()

            val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 15000
                readTimeout = 60000
            }

            try {
                val totalBytes = conn.contentLengthLong
                state = state.copy(totalBytes = totalBytes)
                emit(state)

                conn.inputStream.use { input ->
                    targetFile.outputStream().use { output ->
                        val buffer = ByteArray(8192)
                        var downloaded = 0L
                        var bytesRead: Int

                        while (input.read(buffer).also { bytesRead = it } != -1) {
                            output.write(buffer, 0, bytesRead)
                            downloaded += bytesRead
                            val progress = if (totalBytes > 0) downloaded.toFloat() / totalBytes else 0f
                            state = state.copy(
                                progress = progress,
                                downloadedBytes = downloaded
                            )
                            emit(state)
                        }
                    }
                }

                emit(state.copy(
                    status = DownloadStatus.COMPLETED,
                    progress = 1f,
                    filePath = targetFile.absolutePath
                ))
            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            emit(state.copy(status = DownloadStatus.FAILED))
        }
    }.flowOn(Dispatchers.IO)

    fun installApk(context: Context, filePath: String) {
        val file = File(filePath)
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}