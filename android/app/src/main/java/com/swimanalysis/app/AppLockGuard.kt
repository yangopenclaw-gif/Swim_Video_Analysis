package com.swimanalysis.app

object AppLockGuard {
    @Volatile
    var awaitingExternalActivity: Boolean = false
}