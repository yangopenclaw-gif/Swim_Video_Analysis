package com.swimanalysis.app.ui.screen.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.swimanalysis.app.data.local.AuthStore
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class BootReceiver : BroadcastReceiver() {

    @Inject
    lateinit var scheduleSync: ScheduleSyncManager

    @Inject
    lateinit var authStore: AuthStore

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                if (authStore.currentToken() != null) {
                    scheduleSync.sync()
                }
            } finally {
                pending.finish()
            }
        }
    }
}