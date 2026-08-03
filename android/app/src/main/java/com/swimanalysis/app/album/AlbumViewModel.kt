package com.swimanalysis.app.album

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AlbumUiState(
    val isScanning: Boolean = false,
    val scanProgress: Float = 0f,
    val scanMessage: String = "",
    val totalCount: Int = 0,
    val scannedCount: Int = 0,
    val albums: Map<String, PersonAlbum> = emptyMap(),
    val referenceUris: Map<String, List<Uri>> = emptyMap(),
    val selectedPerson: String? = null,
    val error: String? = null
)

@HiltViewModel
class AlbumViewModel @Inject constructor(
    @ApplicationContext private val context: Context
) : ViewModel() {
    private val _state = MutableStateFlow(AlbumUiState())
    val state: StateFlow<AlbumUiState> = _state.asStateFlow()

    private val faceRecognizer = FaceRecognizer()
    private val photoScanner = PhotoScanner(context, faceRecognizer)

    companion object {
        val PERSONS = listOf("杨钧涵", "杨涴婷")
    }

    fun addReferencePhoto(personName: String, uri: Uri) {
        _state.update { current ->
            val existing = current.referenceUris[personName] ?: emptyList()
            val updated = current.referenceUris.toMutableMap()
            updated[personName] = existing + uri
            current.copy(referenceUris = updated)
        }
    }

    fun removeReferencePhoto(personName: String, uri: Uri) {
        _state.update { current ->
            val existing = current.referenceUris[personName] ?: emptyList()
            val updated = current.referenceUris.toMutableMap()
            updated[personName] = existing - uri
            current.copy(referenceUris = updated)
        }
    }

    fun selectPerson(name: String?) {
        _state.update { it.copy(selectedPerson = name) }
    }

    fun startScan() {
        val referenceUris = _state.value.referenceUris
        val hasReferences = PERSONS.any { (referenceUris[it]?.size ?: 0) > 0 }
        if (!hasReferences) {
            _state.update { it.copy(error = "请先为至少一个孩子添加参考照片") }
            return
        }

        _state.update { it.copy(isScanning = true, error = null, scanMessage = "准备扫描...") }
        viewModelScope.launch {
            photoScanner.scanAlbums(PERSONS, referenceUris).collect { scanState ->
                _state.update {
                    AlbumUiState(
                        isScanning = scanState.status == ScanStatus.SCANNING,
                        scanProgress = scanState.progress,
                        scanMessage = scanState.currentPhoto,
                        totalCount = scanState.totalCount,
                        scannedCount = scanState.scannedCount,
                        albums = scanState.albums,
                        referenceUris = referenceUris,
                        selectedPerson = it.selectedPerson,
                        error = scanState.error
                    )
                }
            }
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }
}