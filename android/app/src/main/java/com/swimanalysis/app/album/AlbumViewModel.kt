package com.swimanalysis.app.album

import android.content.Context
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.local.AlbumStore
import com.swimanalysis.app.data.local.StoredPhoto
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
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
    @ApplicationContext private val context: Context,
    private val albumStore: AlbumStore
) : ViewModel() {
    private val _state = MutableStateFlow(AlbumUiState())
    val state: StateFlow<AlbumUiState> = _state.asStateFlow()

    private val faceRecognizer = FaceRecognizer()
    private val photoScanner = PhotoScanner(context, faceRecognizer)

    companion object {
        val PERSONS = listOf("杨钧涵", "杨涴婷")
    }

    init {
        PERSONS.forEach { person ->
            viewModelScope.launch {
                albumStore.referencePaths(person).collect { paths ->
                    val uris = paths.map { Uri.fromFile(File(it)) }
                    _state.update { it.copy(referenceUris = it.referenceUris + (person to uris)) }
                }
            }
            viewModelScope.launch {
                albumStore.albumPhotos(person).collect { stored ->
                    if (stored.isNotEmpty()) {
                        val photos = stored.map {
                            PersonPhoto(Uri.parse(it.uri), it.uri, it.dateTaken, it.dateText, it.location, it.size)
                        }
                        _state.update { it.copy(albums = it.albums + (person to PersonAlbum(person, emptyList(), photos))) }
                    }
                }
            }
        }
    }

    fun addReferencePhoto(personName: String, uri: Uri) {
        viewModelScope.launch {
            try {
                val destPath = withContext(Dispatchers.IO) {
                    val dir = File(context.filesDir, "refs/$personName").apply { mkdirs() }
                    val dest = File(dir, "${System.currentTimeMillis()}.jpg")
                    context.contentResolver.openInputStream(uri)?.use { ins ->
                        dest.outputStream().use { out -> ins.copyTo(out) }
                    }
                    dest.absolutePath
                }
                val newUri = Uri.fromFile(File(destPath))
                _state.update { current ->
                    val existing = current.referenceUris[personName] ?: emptyList()
                    current.copy(referenceUris = current.referenceUris + (personName to (existing + newUri)))
                }
                val paths = (_state.value.referenceUris[personName] ?: emptyList()).mapNotNull { it.path }
                albumStore.saveReferencePaths(personName, paths)
            } catch (e: Exception) {
                _state.update { it.copy(error = "添加参考照片失败: ${e.message}") }
            }
        }
    }

    fun removeReferencePhoto(personName: String, uri: Uri) {
        viewModelScope.launch {
            withContext(Dispatchers.IO) { runCatching { File(uri.path ?: "").delete() } }
            _state.update { current ->
                val existing = current.referenceUris[personName] ?: emptyList()
                current.copy(referenceUris = current.referenceUris + (personName to (existing - uri)))
            }
            val paths = (_state.value.referenceUris[personName] ?: emptyList()).mapNotNull { it.path }
            albumStore.saveReferencePaths(personName, paths)
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
                if (scanState.status == ScanStatus.COMPLETED) {
                    scanState.albums.forEach { (name, album) ->
                        val stored = album.photos.map {
                            StoredPhoto(it.uri.toString(), it.dateTaken, it.dateText, it.location, it.size)
                        }
                        albumStore.saveAlbumPhotos(name, stored)
                    }
                }
            }
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }
}
