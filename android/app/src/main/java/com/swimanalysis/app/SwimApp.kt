package com.swimanalysis.app

import android.app.Application
import com.swimanalysis.app.core.CrashReporter
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class SwimApp : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashReporter.install(this)
        CrashReporter.uploadPendingIfAny()
    }
}