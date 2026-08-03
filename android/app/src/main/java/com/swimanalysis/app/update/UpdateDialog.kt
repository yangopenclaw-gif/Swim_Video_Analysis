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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import android.content.Context
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class UpdateViewModel @Inject constructor(
    private val downloader: UpdateDownloader
) : ViewModel() {
    private val _downloadState = MutableStateFlow(DownloadState())
    val downloadState: StateFlow<DownloadState> = _downloadState.asStateFlow()

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

    fun reset() {
        _downloadState.value = DownloadState()
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

    when {
        downloadState.status == DownloadStatus.COMPLETED -> {
            AlertDialog(
                onDismissRequest = { viewModel.reset(); onDismiss() },
                title = { Text("下载完成") },
                text = { Text("新版本已下载完成，是否立即安装？") },
                confirmButton = {
                    TextButton(onClick = {
                        viewModel.install(context, downloadState.filePath)
                    }) { Text("立即安装") }
                },
                dismissButton = {
                    TextButton(onClick = { viewModel.reset(); onDismiss() }) { Text("稍后") }
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