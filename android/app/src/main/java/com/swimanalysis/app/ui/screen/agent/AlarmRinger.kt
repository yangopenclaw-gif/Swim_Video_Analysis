package com.swimanalysis.app.ui.screen.agent

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

object AlarmRinger {
    private var player: MediaPlayer? = null
    private var vibrator: Vibrator? = null
    private val handler = Handler(Looper.getMainLooper())
    private var volume = 0.2f

    private val rampUp = object : Runnable {
        override fun run() {
            volume = (volume + 0.15f).coerceAtMost(1f)
            player?.setVolume(volume, volume)
            if (volume < 1f) handler.postDelayed(this, 2000)
        }
    }

    fun start(context: Context) {
        stop()
        volume = 0.2f
        val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
        if (uri != null) {
            player = try {
                MediaPlayer().apply {
                    setAudioAttributes(
                        AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ALARM)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                            .build()
                    )
                    setDataSource(context, uri)
                    isLooping = true
                    setVolume(volume, volume)
                    prepare()
                    start()
                }
            } catch (_: Exception) {
                null
            }
            if (player != null) handler.postDelayed(rampUp, 2000)
        }
        vibrator = obtainVibrator(context)?.apply {
            vibrate(VibrationEffect.createWaveform(longArrayOf(0, 800, 600, 800, 600), 0))
        }
    }

    private fun obtainVibrator(context: Context): Vibrator? {
        return if (Build.VERSION.SDK_INT >= 31) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }

    fun stop() {
        handler.removeCallbacks(rampUp)
        try {
            player?.stop()
        } catch (_: IllegalStateException) {
        }
        player?.release()
        player = null
        vibrator?.cancel()
        vibrator = null
    }
}