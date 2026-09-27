package com.swimanalysis.app.ui.screen.agent

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.swimanalysis.app.R

class ScheduleReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val title = intent.getStringExtra("title") ?: "日程提醒"
        val content = intent.getStringExtra("content").orEmpty()
        val channelId = "schedule_reminder"

        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            manager.createNotificationChannel(
                NotificationChannel(channelId, "日程提醒", NotificationManager.IMPORTANCE_HIGH)
            )
        }

        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(content.ifBlank { "到时间了，记得查看哦" })
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        try {
            NotificationManagerCompat.from(context).notify(title.hashCode(), notification)
        } catch (_: SecurityException) {
            // 未授予通知权限时静默忽略
        }
    }
}