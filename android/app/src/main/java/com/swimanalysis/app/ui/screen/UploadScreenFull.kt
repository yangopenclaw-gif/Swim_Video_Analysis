package com.swimanalysis.app.ui.screen

import android.Manifest
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.swimanalysis.app.media.VideoPicker
import com.swimanalysis.app.ui.navigation.Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UploadScreenFull(
    navController: NavController,
    viewModel: UploadViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    var selectedVideoUri by remember { mutableStateOf<Uri?>(null) }
    var swimmerName by remember { mutableStateOf("") }
    var displayName by remember { mutableStateOf("") }
    var competitionName by remember { mutableStateOf("") }
    var poolLength by remember { mutableStateOf("50") }
    var raceDistance by remember { mutableStateOf("50") }
    var strokeType by remember { mutableStateOf("自由泳") }
    var strokeMenuExpanded by remember { mutableStateOf(false) }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        selectedVideoUri = uri
        if (uri != null && displayName.isEmpty()) {
            displayName = "比赛视频"
        }
    }

    val strokeTypes = listOf("自由泳", "蛙泳", "仰泳", "蝶泳", "混合泳")

    Scaffold(
        topBar = { TopAppBar(title = { Text("上传视频") }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("选择视频", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = { galleryLauncher.launch("video/*") },
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Filled.PlayArrow, contentDescription = null)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("从相册选择")
                        }
                        Button(
                            onClick = { /* 跳转拍摄界面 */ },
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Filled.Videocam, contentDescription = null)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("拍摄视频")
                        }
                    }
                    selectedVideoUri?.let {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "已选择: ${it.lastPathSegment}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            Card(
                modifier = Modifier.fillMaxWidth(),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("分析参数", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = swimmerName,
                        onValueChange = { swimmerName = it },
                        label = { Text("泳者姓名") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = displayName,
                        onValueChange = { displayName = it },
                        label = { Text("视频显示名称") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = competitionName,
                        onValueChange = { competitionName = it },
                        label = { Text("比赛名称") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = poolLength,
                            onValueChange = { poolLength = it.filter { c -> c.isDigit() } },
                            label = { Text("泳池长度(m)") },
                            modifier = Modifier.weight(1f)
                        )
                        OutlinedTextField(
                            value = raceDistance,
                            onValueChange = { raceDistance = it.filter { c -> c.isDigit() } },
                            label = { Text("比赛距离(m)") },
                            modifier = Modifier.weight(1f)
                        )
                    }
                    Box {
                        OutlinedTextField(
                            value = strokeType,
                            onValueChange = { },
                            label = { Text("泳姿") },
                            modifier = Modifier.fillMaxWidth(),
                            readOnly = true,
                            trailingIcon = {
                                TextButton(onClick = { strokeMenuExpanded = true }) {
                                    Text("选择")
                                }
                            }
                        )
                        DropdownMenu(
                            expanded = strokeMenuExpanded,
                            onDismissRequest = { strokeMenuExpanded = false }
                        ) {
                            strokeTypes.forEach { type ->
                                DropdownMenuItem(
                                    text = { Text(type) },
                                    onClick = {
                                        strokeType = type
                                        strokeMenuExpanded = false
                                    }
                                )
                            }
                        }
                    }
                }
            }

            if (state.isUploading) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("上传进度", style = MaterialTheme.typography.titleSmall)
                        Spacer(modifier = Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = state.uploadProgress,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "${(state.uploadProgress * 100).toInt()}% - ${state.uploadMessage}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }

            Button(
                onClick = {
                    val uri = selectedVideoUri ?: return@Button
                    val file = VideoPicker.uriToFile(context, uri) ?: return@Button
                    viewModel.startUpload(
                        file = file,
                        athleteName = swimmerName,
                        displayName = displayName,
                        competitionName = competitionName
                    )
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = selectedVideoUri != null && swimmerName.isNotEmpty() && !state.isUploading
            ) {
                Text("开始上传并分析")
            }

            if (state.taskId.isNotEmpty() && !state.isUploading) {
                Button(
                    onClick = {
                        navController.navigate(Screen.AnalyzeProgress.withArgs(state.taskId))
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("查看分析进度")
                }
            }
        }
    }
}

private fun Modifier.width(dp: androidx.compose.ui.unit.Dp) = this.then(
    androidx.compose.foundation.layout.Modifier.padding(start = dp)
)