package com.swimanalysis.app.ui.screen

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.RecordDto
import com.swimanalysis.app.data.model.VideoDto
import com.swimanalysis.app.data.repository.SwimRepository
import com.swimanalysis.app.upload.ChunkUploader
import com.swimanalysis.app.upload.UploadState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

data class RecordsUiState(
    val isLoading: Boolean = false,
    val records: List<RecordDto> = emptyList(),
    val error: String? = null,
    val isAdding: Boolean = false,
    val addSuccess: Boolean = false
)

@HiltViewModel
class RecordsViewModel @Inject constructor(
    private val repository: SwimRepository
) : ViewModel() {
    private val _state = MutableStateFlow(RecordsUiState(isLoading = true))
    val state: StateFlow<RecordsUiState> = _state.asStateFlow()

    init {
        loadRecords()
    }

    fun loadRecords() {
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            try {
                val records = repository.getAllRecords()
                _state.update { it.copy(isLoading = false, records = records) }
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    fun addManualRecord(
        swimmerName: String, poolLength: Int, raceDistance: Int, strokeType: String,
        raceName: String, raceDate: String, raceLocation: String, totalTime: String
    ) {
        _state.update { it.copy(isAdding = true, error = null) }
        viewModelScope.launch {
            try {
                repository.manualRecord(
                    swimmerName, poolLength, raceDistance, strokeType,
                    swimmerPosition = 0, raceName, raceDate, raceLocation, totalTime
                )
                _state.update { it.copy(isAdding = false, addSuccess = true) }
                loadRecords()
            } catch (e: Exception) {
                _state.update { it.copy(isAdding = false, error = e.message) }
            }
        }
    }

    fun clearAddSuccess() {
        _state.update { it.copy(addSuccess = false) }
    }
}

data class UploadUiState(
    val isUploading: Boolean = false,
    val uploadProgress: Float = 0f,
    val uploadMessage: String = "",
    val taskId: String = "",
    val videoId: String = ""
)

@HiltViewModel
class UploadViewModel @Inject constructor(
    private val uploader: ChunkUploader
) : ViewModel() {
    private val _state = MutableStateFlow(UploadUiState())
    val state: StateFlow<UploadUiState> = _state.asStateFlow()

    fun startUpload(
        file: File,
        athleteName: String,
        displayName: String,
        competitionName: String
    ) {
        viewModelScope.launch {
            uploader.upload(file, athleteName, displayName, competitionName).collect { uploadState ->
                _state.update {
                    UploadUiState(
                        isUploading = uploadState.status == com.swimanalysis.app.upload.UploadStatus.UPLOADING,
                        uploadProgress = uploadState.progress,
                        uploadMessage = uploadState.message,
                        taskId = uploadState.taskId,
                        videoId = uploadState.videoId
                    )
                }
            }
        }
    }
}

data class VideosUiState(
    val isLoading: Boolean = false,
    val videos: List<VideoDto> = emptyList(),
    val error: String? = null
)

@HiltViewModel
class VideosViewModel @Inject constructor(
    private val repository: SwimRepository
) : ViewModel() {
    private val _state = MutableStateFlow(VideosUiState(isLoading = true))
    val state: StateFlow<VideosUiState> = _state.asStateFlow()

    init {
        loadVideos()
    }

    fun loadVideos() {
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            try {
                val videos = repository.getVideos()
                _state.update { it.copy(isLoading = false, videos = videos) }
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }
}