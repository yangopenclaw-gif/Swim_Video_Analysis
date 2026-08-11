package com.swimanalysis.app.ui.screen

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.BuildConfig
import com.swimanalysis.app.data.repository.SwimRepository
import com.swimanalysis.app.update.DownloadStatus
import com.swimanalysis.app.update.UpdateChecker
import com.swimanalysis.app.update.UpdateDownloader
import com.swimanalysis.app.update.UpdateInfo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import javax.inject.Inject

data class SettingsUiState(
    val isTesting: Boolean = false,
    val testResult: String = "",
    val testSuccess: Boolean = false,
    val isCheckingUpdate: Boolean = false,
    val updateInfo: UpdateInfo? = null,
    val updateError: String? = null,
    val apkDownloadStatus: DownloadStatus = DownloadStatus.IDLE,
    val apkDownloadProgress: Float = 0f,
    val apkFilePath: String = "",
    val apkDownloadError: String? = null
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: SwimRepository,
    private val updateChecker: UpdateChecker,
    private val downloader: UpdateDownloader
) : ViewModel() {
    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    fun testConnection(serverUrl: String) {
        _state.update { it.copy(isTesting = true, testResult = "测试中...", testSuccess = false) }
        viewModelScope.launch {
            try {
                val healthUrl = serverUrl.trimEnd('/') + "/api/health"
                val result = withContext(Dispatchers.IO) {
                    val url = URL(healthUrl)
                    val conn = url.openConnection() as HttpURLConnection
                    conn.connectTimeout = 5000
                    conn.readTimeout = 10000
                    try {
                        val code = conn.responseCode
                        if (code == 200) {
                            val body = conn.inputStream.bufferedReader().use { it.readText() }
                            "连接成功 (HTTP $code)\n响应: $body"
                        } else {
                            "连接失败 (HTTP $code)"
                        }
                    } finally {
                        conn.disconnect()
                    }
                }
                _state.update {
                    it.copy(isTesting = false, testResult = result, testSuccess = result.contains("成功"))
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(isTesting = false, testResult = "连接失败: ${e.message}", testSuccess = false)
                }
            }
        }
    }

    fun checkUpdate() {
        _state.update { it.copy(isCheckingUpdate = true, updateError = null) }
        viewModelScope.launch {
            try {
                val info = updateChecker.checkForUpdate()
                _state.update { it.copy(isCheckingUpdate = false, updateInfo = info) }
            } catch (e: Exception) {
                _state.update { it.copy(isCheckingUpdate = false, updateError = e.message) }
            }
        }
    }

    fun clearUpdateInfo() {
        _state.update { it.copy(updateInfo = null, updateError = null) }
    }

    fun downloadCurrentApk(context: Context) {
        if (_state.value.apkDownloadStatus == DownloadStatus.DOWNLOADING) return
        _state.update {
            it.copy(apkDownloadStatus = DownloadStatus.DOWNLOADING, apkDownloadProgress = 0f, apkDownloadError = null)
        }
        viewModelScope.launch {
            try {
                val url = updateChecker.getAssetDownloadUrl(BuildConfig.VERSION_NAME)
                if (url.isEmpty()) {
                    _state.update {
                        it.copy(apkDownloadStatus = DownloadStatus.FAILED, apkDownloadError = "当前版本未找到APK文件")
                    }
                    return@launch
                }
                downloader.download(context, url).collect { ds ->
                    _state.update {
                        it.copy(
                            apkDownloadStatus = ds.status,
                            apkDownloadProgress = ds.progress,
                            apkFilePath = ds.filePath,
                            apkDownloadError = if (ds.status == DownloadStatus.FAILED) "下载失败，请检查网络" else it.apkDownloadError
                        )
                    }
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(apkDownloadStatus = DownloadStatus.FAILED, apkDownloadError = "获取下载地址失败: ${e.message}")
                }
            }
        }
    }

    fun installCurrentApk(context: Context) {
        val filePath = _state.value.apkFilePath
        if (filePath.isNotEmpty()) {
            downloader.installApk(context, filePath)
        }
    }

    fun resetApkDownload() {
        _state.update {
            it.copy(apkDownloadStatus = DownloadStatus.IDLE, apkDownloadProgress = 0f, apkFilePath = "", apkDownloadError = null)
        }
    }
}