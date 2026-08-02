package com.swimanalysis.app.media

import android.content.Context
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class VideoCompressor @Inject constructor() {

    fun getVideoDurationMs(context: Context, uri: Uri): Long {
        return try {
            val player = ExoPlayer.Builder(context).build()
            player.setMediaItem(MediaItem.fromUri(uri))
            player.prepare()
            val duration = player.duration
            player.release()
            if (duration > 0) duration else 0L
        } catch (e: Exception) {
            0L
        }
    }

    fun getVideoDurationMs(context: Context, file: File): Long {
        return getVideoDurationMs(context, Uri.fromFile(file))
    }

    fun formatDuration(ms: Long): String {
        val sec = ms / 1000
        return "%d:%02d".format(sec / 60, sec % 60)
    }
}