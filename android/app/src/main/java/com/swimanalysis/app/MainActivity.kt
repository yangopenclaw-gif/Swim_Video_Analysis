package com.swimanalysis.app

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.ProcessLifecycleOwner
import com.swimanalysis.app.data.local.AuthStore
import com.swimanalysis.app.ui.SwimNavHost
import com.swimanalysis.app.ui.screen.LockScreen
import com.swimanalysis.app.ui.screen.LoginScreen
import com.swimanalysis.app.ui.theme.SwimAnalysisTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : FragmentActivity() {

    @Inject
    lateinit var authStore: AuthStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStop(owner: LifecycleOwner) {
                authStore.lock()
            }
        })
        setContent {
            SwimAnalysisTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val isLoggedIn by authStore.isLoggedIn.collectAsState()
                    val locked by authStore.locked.collectAsState()
                    when {
                        isLoggedIn == false -> LoginScreen()
                        isLoggedIn == true && locked -> LockScreen()
                        isLoggedIn == true -> SwimNavHost()
                        else -> {}
                    }
                }
            }
        }
    }
}