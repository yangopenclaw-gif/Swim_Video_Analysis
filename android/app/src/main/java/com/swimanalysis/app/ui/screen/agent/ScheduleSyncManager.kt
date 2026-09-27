package com.swimanalysis.app.ui.screen.agent

import android.content.Context
import com.swimanalysis.app.data.repository.AgentRepository
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ScheduleSyncManager @Inject constructor(
    @ApplicationContext private val context: Context,
    private val repository: AgentRepository
) {
    suspend fun sync() {
        try {
            val schedules = repository.listSchedules()
            ScheduleAlarmManager.sync(context, schedules)
        } catch (_: Exception) {
            // 同步失败时静默忽略，不打断主流程
        }
    }
}