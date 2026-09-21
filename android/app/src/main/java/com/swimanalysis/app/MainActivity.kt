package com.swimanalysis.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import com.swimanalysis.app.data.local.AuthStore
import com.swimanalysis.app.ui.SwimNavHost
import com.swimanalysis.app.ui.screen.LoginScreen
import com.swimanalysis.app.ui.theme.SwimAnalysisTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var authStore: AuthStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            SwimAnalysisTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val isLoggedIn by authStore.isLoggedIn.collectAsState()
                    when (isLoggedIn) {
                        true -> SwimNavHost()
                        false -> LoginScreen()
                        null -> {}
                    }
                }
            }
        }
    }
}