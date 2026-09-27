package com.swimanalysis.app.ui.screen.agent

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import com.swimanalysis.app.data.model.ScheduleDto
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

object ScheduleAlarmManager {
    private const val PREFS = "schedule_alarms"
    private const val KEY_IDS = "alarm_ids"
    private val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")

    fun sync(context: Context, schedules: List<ScheduleDto>) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val oldIds = prefs.getStringSet(KEY_IDS, emptySet()) ?: emptySet()

        for (id in oldIds) {
            alarmManager.cancel(blankPendingIntent(context, id))
        }

        val newIds = mutableSetOf<String>()
        val now = System.currentTimeMillis()
        for (s in schedules) {
            val time = parseRemindAt(s.remindAt) ?: continue
            if (time <= now) continue
            val pi = PendingIntent.getBroadcast(
                context, s.id.hashCode(),
                Intent(context, ScheduleReceiver::class.java).apply {
                    putExtra("title", s.title)
                    putExtra("content", s.content)
                },
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            alarmManager.setWindow(AlarmManager.RTC_WAKEUP, time, 60_000L, pi)
            newIds.add(s.id)
        }

        prefs.edit().putStringSet(KEY_IDS, newIds).apply()
    }

    private fun blankPendingIntent(context: Context, id: String): PendingIntent {
        return PendingIntent.getBroadcast(
            context, id.hashCode(),
            Intent(context, ScheduleReceiver::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    fun parseRemindAt(text: String): Long? {
        return try {
            LocalDateTime.parse(text, formatter)
                .atZone(ZoneId.systemDefault())
                .toInstant()
                .toEpochMilli()
        } catch (e: Exception) {
            null
        }
    }
}