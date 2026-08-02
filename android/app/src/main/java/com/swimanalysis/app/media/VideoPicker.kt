package com.swimanalysis.app.media

import android.content.Context
import android.net.Uri
import android.provider.MediaStore
import androidx.core.content.FileProvider
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object VideoPicker {

    fun createVideoFile(context: Context): File {
        val timeStamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.CHINA).format(Date())
        val storageDir = File(context.filesDir, "videos")
        if (!storageDir.exists()) storageDir.mkdirs()
        return File(storageDir, "VIDEO_${timeStamp}.mp4")
    }

    fun getVideoUriForCamera(context: Context, file: File): Uri {
        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file
        )
    }

    fun queryGalleryVideos(context: Context): List<GalleryVideo> {
        val videos = mutableListOf<GalleryVideo>()
        val projection = arrayOf(
            MediaStore.Video.Media._ID,
            MediaStore.Video.Media.DISPLAY_NAME,
            MediaStore.Video.Media.DURATION,
            MediaStore.Video.Media.SIZE,
            MediaStore.Video.Media.DATE_ADDED,
            MediaStore.Video.Media.DATA
        )
        val sortOrder = "${MediaStore.Video.Media.DATE_ADDED} DESC"

        context.contentResolver.query(
            MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
            projection,
            null,
            null,
            sortOrder
        )?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media._ID)
            val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DISPLAY_NAME)
            val durationCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DURATION)
            val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.SIZE)
            val dateCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DATE_ADDED)
            val dataCol = cursor.getColumnIndexOrThrow(MediaStore.Video.Media.DATA)

            while (cursor.moveToNext()) {
                val id = cursor.getLong(idCol)
                val name = cursor.getString(nameCol) ?: continue
                val duration = cursor.getLong(durationCol)
                val size = cursor.getLong(sizeCol)
                val dateAdded = cursor.getLong(dateCol)
                val path = cursor.getString(dataCol) ?: continue
                val uri = Uri.withAppendedPath(
                    MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                    id.toString()
                )
                videos.add(GalleryVideo(uri, name, path, duration, size, dateAdded))
            }
        }
        return videos
    }

    fun uriToFile(context: Context, uri: Uri): File? {
        val targetFile = createVideoFile(context)
        return try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                targetFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            targetFile
        } catch (e: Exception) {
            null
        }
    }
}

data class GalleryVideo(
    val uri: Uri,
    val name: String,
    val path: String,
    val duration: Long,
    val size: Long,
    val dateAdded: Long
) {
    val durationText: String
        get() {
            val sec = duration / 1000
            return "%d:%02d".format(sec / 60, sec % 60)
        }

    val sizeText: String
        get() = when {
            size >= 1024 * 1024 * 1024 -> "%.1f GB".format(size.toFloat() / (1024 * 1024 * 1024))
            size >= 1024 * 1024 -> "%.1f MB".format(size.toFloat() / (1024 * 1024))
            size >= 1024 -> "%.1f KB".format(size.toFloat() / 1024)
            else -> "$size B"
        }
}