package com.swimanalysis.app.ui

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.outlined.Analytics
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.swimanalysis.app.ui.navigation.Screen
import com.swimanalysis.app.ui.screen.AnalyzeProgressScreenFull
import com.swimanalysis.app.ui.screen.AiRecognizeScreenFull
import com.swimanalysis.app.ui.screen.CompareScreenFull
import com.swimanalysis.app.ui.screen.CompetitionsScreen
import com.swimanalysis.app.ui.screen.HomeScreen
import com.swimanalysis.app.ui.screen.RecordDetailScreen
import com.swimanalysis.app.ui.screen.RecordsScreen
import com.swimanalysis.app.ui.screen.SettingsScreenFull
import com.swimanalysis.app.ui.screen.SwimmerRecordsScreen
import com.swimanalysis.app.ui.screen.UploadScreenFull
import com.swimanalysis.app.ui.screen.VideoAnnotateScreenFull
import com.swimanalysis.app.ui.screen.VideoPlayerScreenFull
import com.swimanalysis.app.ui.screen.VideosScreen
import com.swimanalysis.app.ui.screen.ProfileScreen
import com.swimanalysis.app.album.AlbumScreen
import com.swimanalysis.app.ui.screen.ledger.AddEntryScreen
import com.swimanalysis.app.ui.screen.ledger.LedgerScreen
import com.swimanalysis.app.ui.screen.ledger.StatsScreen

private data class BottomItem(
    val screen: Screen,
    val icon: ImageVector,
    val label: String
)

private val bottomItems = listOf(
    BottomItem(Screen.Stats, Icons.Outlined.Analytics, "统计"),
    BottomItem(Screen.Ledger, Icons.Filled.ReceiptLong, "账单"),
    BottomItem(Screen.Profile, Icons.Filled.Person, "我的")
)

@Composable
fun SwimNavHost() {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    val showBottomBar = bottomItems.any { it.screen.route == currentRoute }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    bottomItems.forEach { item ->
                        val selected = backStackEntry?.destination?.hierarchy?.any {
                            it.route == item.screen.route
                        } == true
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navController.navigate(item.screen.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(item.icon, contentDescription = item.label) },
                            label = { Text(item.label) }
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Stats.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Ledger.route) { LedgerScreen(navController) }
            composable(Screen.Stats.route) { StatsScreen() }
            composable(Screen.AddEntry.route) { AddEntryScreen(navController) }

            composable(Screen.Home.route) { HomeScreen(navController) }
            composable(Screen.Records.route) { RecordsScreen(navController) }
            composable(Screen.Upload.route) { UploadScreenFull(navController) }
            composable(Screen.Videos.route) { VideosScreen(navController) }
            composable(Screen.Album.route) { AlbumScreen(navController) }
            composable(Screen.Profile.route) { ProfileScreen(navController) }

            composable(Screen.RecordDetail.route) { backStack ->
                val recordId = backStack.arguments?.getString("recordId") ?: ""
                RecordDetailScreen(navController, recordId)
            }
            composable(Screen.SwimmerRecords.route) { backStack ->
                val name = backStack.arguments?.getString("name") ?: ""
                SwimmerRecordsScreen(navController, name)
            }
            composable(Screen.VideoPlayer.route) { backStack ->
                val videoId = backStack.arguments?.getString("videoId") ?: ""
                VideoPlayerScreenFull(navController, videoId)
            }
            composable(Screen.VideoAnnotate.route) { backStack ->
                val videoId = backStack.arguments?.getString("videoId") ?: ""
                VideoAnnotateScreenFull(navController, videoId)
            }
            composable(Screen.AnalyzeProgress.route) { backStack ->
                val taskId = backStack.arguments?.getString("taskId") ?: ""
                AnalyzeProgressScreenFull(navController, taskId)
            }
            composable(Screen.Compare.route) { CompareScreenFull(navController) }
            composable(Screen.Competitions.route) { CompetitionsScreen(navController) }
            composable(Screen.AiRecognize.route) { AiRecognizeScreenFull(navController) }
            composable(Screen.Settings.route) { SettingsScreenFull(navController) }
        }
    }
}
