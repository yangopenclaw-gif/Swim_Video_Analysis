package com.swimanalysis.app.ui.screen.agent

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.swimanalysis.app.R

class ScheduleReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val title = intent.getStringExtra("title") ?: "日程提醒"
        val content = intent.getStringExtra("content").orEmpty()
        val scheduleId = intent.getStringExtra("id").orEmpty()
        val notifyId = scheduleId.ifBlank { title }.hashCode()
        val channelId = "schedule_alarm"
        val soundUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.deleteNotificationChannel(channelId)
        val channel = NotificationChannel(channelId, "日程提醒", NotificationManager.IMPORTANCE_HIGH).apply {
            setSound(
                soundUri,
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 800, 600, 800)
        }
        manager.createNotificationChannel(channel)

        val fullScreenIntent = PendingIntent.getActivity(
            context, notifyId,
            Intent(context, AlarmActivity::class.java).apply {
                putExtra("title", title)
                putExtra("content", content)
                putExtra("id", scheduleId)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(content.ifBlank { "到时间了，记得查看哦" })
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setContentIntent(fullScreenIntent)
            .setFullScreenIntent(fullScreenIntent, true)
            .setAutoCancel(true)
            .build()

        try {
            NotificationManagerCompat.from(context).notify(notifyId, notification)
        } catch (_: SecurityException) {
        }
    }
}