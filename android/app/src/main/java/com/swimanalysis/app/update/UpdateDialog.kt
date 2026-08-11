package com.swimanalysis.app.update

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import android.content.Context
import android.widget.Toast
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

@HiltViewModel
class UpdateViewModel @Inject constructor(
    private val downloader: UpdateDownloader
) : ViewModel() {
    private val _downloadState = MutableStateFlow(DownloadState())
    val downloadState: StateFlow<DownloadState> = _downloadState.asStateFlow()

    private val _saveAsState = MutableStateFlow<String?>(null)
    val saveAsState: StateFlow<String?> = _saveAsState.asStateFlow()

    fun startDownload(context: Context, url: String) {
        viewModelScope.launch {
            downloader.download(context, url).collect { state ->
                _downloadState.value = state
            }
        }
    }

    fun install(context: Context, filePath: String) {
        downloader.installApk(context, filePath)
    }

    fun saveAs(context: Context, filePath: String) {
        viewModelScope.launch {
            val saved = withContext(Dispatchers.IO) {
                downloader.saveApkAs(context, filePath)
            }
            _saveAsState.value = if (saved != null) "已保存到系统下载目录" else "另存为失败，请重试"
        }
    }

    fun clearSaveAsState() {
        _saveAsState.value = null
    }

    fun reset() {
        _downloadState.value = DownloadState()
        _saveAsState.value = null
    }
}

@Composable
fun UpdateDialog(
    updateInfo: UpdateInfo,
    onDismiss: () -> Unit,
    viewModel: UpdateViewModel = hiltViewModel()
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val downloadState by viewModel.downloadState.collectAsState()
    val saveAsState by viewModel.saveAsState.collectAsState()

    LaunchedEffect(saveAsState) {
        saveAsState?.let {
            Toast.makeText(context, it, Toast.LENGTH_LONG).show()
            viewModel.clearSaveAsState()
        }
    }

    when {
        downloadState.status == DownloadStatus.COMPLETED -> {
            AlertDialog(
                onDismissRequest = { viewModel.reset(); onDismiss() },
                title = { Text("下载完成") },
                text = {
                    Column {
                        Text("新版本已下载完成，是否立即安装？")
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "也可另存为APK文件到系统下载目录，方便以后安装",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                confirmButton = {
                    TextButton(onClick = {
                        viewModel.install(context, downloadState.filePath)
                    }) { Text("立即安装") }
                },
                dismissButton = {
                    Row {
                        TextButton(onClick = {
                            viewModel.saveAs(context, downloadState.filePath)
                        }) { Text("另存为") }
                        TextButton(onClick = { viewModel.reset(); onDismiss() }) { Text("稍后") }
                    }
                }
            )
        }
        downloadState.status == DownloadStatus.DOWNLOADING -> {
            AlertDialog(
                onDismissRequest = { },
                title = { Text("正在下载更新...") },
                text = {
                    Column {
                        LinearProgressIndicator(
                            progress = downloadState.progress,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "${(downloadState.progress * 100).toInt()}%  " +
                                formatBytes(downloadState.downloadedBytes) +
                                " / " + formatBytes(downloadState.totalBytes),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                },
                confirmButton = { },
                dismissButton = { }
            )
        }
        downloadState.status == DownloadStatus.FAILED -> {
            AlertDialog(
                onDismissRequest = { viewModel.reset(); onDismiss() },
                title = { Text("下载失败") },
                text = { Text("无法下载更新，请检查网络后重试") },
                confirmButton = {
                    TextButton(onClick = { viewModel.reset() }) { Text("重试") }
                },
                dismissButton = {
                    TextButton(onClick = { viewModel.reset(); onDismiss() }) { Text("取消") }
                }
            )
        }
        else -> {
            AlertDialog(
                onDismissRequest = onDismiss,
                title = { Text("发现新版本 v${updateInfo.latestVersion}") },
                text = {
                    Column {
                        Text(
                            text = updateInfo.releaseNotes,
                            style = MaterialTheme.typography.bodyMedium
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        if (updateInfo.fileSize > 0) {
                            Text(
                                text = "大小: ${formatBytes(updateInfo.fileSize)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                confirmButton = {
                    TextButton(onClick = {
                        viewModel.startDownload(context, updateInfo.downloadUrl)
                    }) { Text("立即更新") }
                },
                dismissButton = {
                    TextButton(onClick = onDismiss) { Text("稍后") }
                }
            )
        }
    }
}

private fun formatBytes(bytes: Long): String {
    return when {
        bytes >= 1024 * 1024 -> "%.1f MB".format(bytes.toFloat() / (1024 * 1024))
        bytes >= 1024 -> "%.1f KB".format(bytes.toFloat() / 1024)
        else -> "$bytes B"
    }
}