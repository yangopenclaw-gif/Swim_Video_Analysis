package com.swimanalysis.app.ui.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.navigation.NavController
import com.swimanalysis.app.BuildConfig
import com.swimanalysis.app.data.model.MarkerDto
import com.swimanalysis.app.data.repository.SwimRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class VideoAnnotateState(
    val markers: List<MarkerDto> = emptyList(),
    val currentTime: Double = 0.0,
    val isLoading: Boolean = false
)

@HiltViewModel
class VideoAnnotateViewModel @Inject constructor(
    private val repository: SwimRepository
) : ViewModel() {
    private val _state = MutableStateFlow(VideoAnnotateState(isLoading = true))
    val state: StateFlow<VideoAnnotateState> = _state.asStateFlow()

    fun loadMarkers(videoId: String) {
        viewModelScope.launch {
            try {
                val markers = repository.getMarkers(videoId)
                _state.value = VideoAnnotateState(markers = markers)
            } catch (e: Exception) {
                _state.value = VideoAnnotateState()
            }
        }
    }

    fun addMarker(videoId: String, timeSeconds: Double, label: String, color: String, key: String) {
        viewModelScope.launch {
            try {
                val marker = repository.addMarker(videoId, timeSeconds, label, color, key)
                _state.value = _state.value.copy(markers = _state.value.markers + marker)
            } catch (_: Exception) {}
        }
    }

    fun deleteMarker(videoId: String, markerId: String) {
        viewModelScope.launch {
            try {
                repository.deleteMarker(videoId, markerId)
                _state.value = _state.value.copy(
                    markers = _state.value.markers.filter { it.id != markerId }
                )
            } catch (_: Exception) {}
        }
    }

    fun detectStart(videoId: String) {
        viewModelScope.launch {
            try {
                repository.detectStartSignal(videoId)
            } catch (_: Exception) {}
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VideoAnnotateScreenFull(
    navController: NavController,
    videoId: String,
    viewModel: VideoAnnotateViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current

    val exoPlayer = remember {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri("${BuildConfig.SERVER_BASE_URL}/api/videos/$videoId/stream"))
            prepare()
        }
    }

    DisposableEffect(Unit) {
        viewModel.loadMarkers(videoId)
        onDispose { exoPlayer.release() }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("视频标注") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(8.dp)
        ) {
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        player = exoPlayer
                        useController = true
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(16f / 9f)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Button(
                    onClick = {
                        val t = exoPlayer.currentPosition / 1000.0
                        viewModel.addMarker(videoId, t, "出发", "#FF0000", "start")
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("标记出发") }
                Button(
                    onClick = {
                        val t = exoPlayer.currentPosition / 1000.0
                        viewModel.addMarker(videoId, t, "转身", "#FFA500", "turn")
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("标记转身") }
                Button(
                    onClick = {
                        val t = exoPlayer.currentPosition / 1000.0
                        viewModel.addMarker(videoId, t, "到边", "#00FF00", "finish")
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("标记到边") }
            }

            Spacer(modifier = Modifier.height(4.dp))
            Button(
                onClick = { viewModel.detectStart(videoId) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Filled.PlayArrow, contentDescription = null)
                Text("自动检测出发信号")
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text("标记列表 (${state.markers.size})", style = MaterialTheme.typography.titleSmall)

            state.markers.forEach { marker ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 2.dp),
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Filled.Flag, contentDescription = null, tint = androidx.compose.ui.graphics.Color(android.graphics.Color.parseColor(marker.color).toLong()))
                            Spacer(modifier = Modifier.height(4.dp))
                            Column {
                                Text(marker.label, style = MaterialTheme.typography.bodyMedium)
                                Text(
                                    text = "%.2f秒".format(marker.timeSeconds),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                        IconButton(onClick = { viewModel.deleteMarker(videoId, marker.id) }) {
                            Icon(Icons.Filled.Delete, contentDescription = "删除")
                        }
                    }
                }
            }
        }
    }
}

private fun Modifier.weight(f: Float) = this.then(
    androidx.compose.foundation.layout.Modifier.fillMaxWidth(f)
)