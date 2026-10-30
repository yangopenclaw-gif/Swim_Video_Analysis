package com.swimanalysis.app.ui.screen.agent

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.repository.AgentRepository
import com.swimanalysis.app.voice.VoiceCallManager
import com.swimanalysis.app.voice.VoiceEvent
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class VoicePhase { CONNECTING, TALKING, CLOSED }

data class VoiceUiState(
    val phase: VoicePhase = VoicePhase.CLOSED,
    val error: String? = null,
    val botSubtitle: String = "",
    val userSubtitle: String = "",
    val botOnline: Boolean = false
)

@HiltViewModel
class VoiceCallViewModel @Inject constructor(
    private val repository: AgentRepository,
    private val manager: VoiceCallManager
) : ViewModel() {

    private val _state = MutableStateFlow(VoiceUiState())
    val state: StateFlow<VoiceUiState> = _state.asStateFlow()

    private var sessionJob: Job? = null
    private var taskId: String? = null
    private var roomId: String? = null

    init {
        sessionJob = viewModelScope.launch {
            manager.events.collect { ev ->
                when (ev) {
                    is VoiceEvent.Connected -> _state.update { it.copy(phase = VoicePhase.TALKING) }
                    is VoiceEvent.Disconnected -> _state.update { it.copy(botOnline = false) }
                    is VoiceEvent.BotJoined -> _state.update { it.copy(botOnline = true, phase = VoicePhase.TALKING) }
                    is VoiceEvent.Subtitle -> _state.update {
                        if (ev.fromBot) it.copy(botSubtitle = ev.text)
                        else it.copy(userSubtitle = ev.text)
                    }
                    is VoiceEvent.Error -> _state.update { it.copy(error = ev.message) }
                }
            }
        }
    }

    fun start() {
        if (_state.value.phase != VoicePhase.CLOSED) return
        _state.update { VoiceUiState(phase = VoicePhase.CONNECTING) }
        viewModelScope.launch {
            try {
                val s = repository.startVoiceSession(null)
                taskId = s.taskId
                roomId = s.roomId
                manager.start(s.appId, s.roomId, s.userId, s.token, s.botUserId)
                _state.update { it.copy(phase = VoicePhase.TALKING) }
            } catch (e: Exception) {
                _state.update { it.copy(phase = VoicePhase.CLOSED, error = e.message ?: "连接失败") }
            }
        }
    }

    fun end() {
        viewModelScope.launch {
            val t = taskId
            val r = roomId
            manager.stop()
            if (t != null && r != null) {
                try {
                    repository.stopVoiceSession(t, r)
                } catch (_: Exception) {
                }
            }
            taskId = null
            roomId = null
            _state.update { VoiceUiState(phase = VoicePhase.CLOSED) }
        }
    }

    fun clearError() = _state.update { it.copy(error = null) }

    override fun onCleared() {
        manager.stop()
        sessionJob?.cancel()
        super.onCleared()
    }
}

@Composable
fun VoiceCallScreen(
    viewModel: VoiceCallViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    LaunchedEffect(Unit) { viewModel.start() }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(Color(0xFF16264F), Color(0xFF070B18))))
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.height(48.dp))
            VoiceAvatar(talking = state.phase == VoicePhase.TALKING && state.botOnline)
            Spacer(Modifier.height(28.dp))
            Text(
                when {
                    state.phase == VoicePhase.CONNECTING -> "正在接通小咩…"
                    state.botOnline -> "通话中 · 随时开口说"
                    else -> "等待小咩上线…"
                },
                color = Color(0xFF9FB0D8), fontSize = 15.sp
            )
            Spacer(Modifier.height(32.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(18.dp))
                    .background(Color(0x14FFFFFF))
                    .padding(horizontal = 18.dp, vertical = 14.dp),
                contentAlignment = Alignment.Center
            ) {
                if (state.userSubtitle.isNotBlank()) {
                    Text(
                        "你：${state.userSubtitle}",
                        color = Color(0xFF8899C4), fontSize = 14.sp, textAlign = TextAlign.Center
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    .clip(RoundedCornerShape(18.dp))
                    .background(Color(0x1FFFFFFF))
                    .padding(horizontal = 18.dp, vertical = 14.dp),
                contentAlignment = Alignment.Center
            ) {
                if (state.botSubtitle.isNotBlank()) {
                    Text(
                        state.botSubtitle,
                        color = Color.White, fontSize = 17.sp, lineHeight = 26.sp,
                        textAlign = TextAlign.Center
                    )
                } else {
                    Text(
                        if (state.phase == VoicePhase.CONNECTING) "…" else "小咩在听",
                        color = Color(0xFF66759E), fontSize = 15.sp
                    )
                }
            }
            state.error?.let {
                Spacer(Modifier.height(12.dp))
                Text("⚠ $it", color = Color(0xFFFFB86B), fontSize = 13.sp, textAlign = TextAlign.Center)
            }
            Spacer(Modifier.weight(1f))
            IconButton(
                onClick = { viewModel.end() },
                modifier = Modifier
                    .size(76.dp)
                    .clip(CircleShape)
                    .background(Brush.verticalGradient(listOf(Color(0xFFE5484D), Color(0xFFB3261E))))
            ) {
                Icon(Icons.Filled.CallEnd, contentDescription = "挂断", tint = Color.White, modifier = Modifier.size(34.dp))
            }
            Spacer(Modifier.height(12.dp))
            Text("挂断", color = Color(0xFF8899C4), fontSize = 13.sp)
            Spacer(Modifier.height(24.dp))
        }
    }

    if (state.phase == VoicePhase.CLOSED) {
        LaunchedEffect(Unit) { }
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xF2070B18)),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("通话已结束", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Medium)
                Spacer(Modifier.height(8.dp))
                Text("本次对话已保存到历史会话", color = Color(0xFF8899C4), fontSize = 13.sp)
            }
        }
    }
}

@Composable
private fun VoiceAvatar(talking: Boolean) {
    val transition = rememberInfiniteTransition(label = "wave")
    val scales = (0 until 5).map { i ->
        transition.animateFloat(
            initialValue = 0.3f,
            targetValue = 1f,
            animationSpec = infiniteRepeatable(
                animation = tween(500 + i * 90, easing = LinearEasing),
                repeatMode = RepeatMode.Reverse
            ),
            label = "bar$i"
        ).value
    }
    Box(contentAlignment = Alignment.Center) {
        if (talking) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                scales.forEach { s ->
                    Box(
                        modifier = Modifier
                            .width(5.dp)
                            .height((14 + 42 * s).dp)
                            .clip(RoundedCornerShape(3.dp))
                            .background(Brush.verticalGradient(listOf(Color(0xFFFFB86B), Color(0xFFF0722B))))
                    )
                }
            }
        }
        Box(
            modifier = Modifier.size(88.dp),
            contentAlignment = Alignment.Center
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(CircleShape)
                    .background(Brush.linearGradient(listOf(Color(0xFFFF9E5E), Color(0xFFF0722B))))
            )
            Text("咩", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Bold)
        }
    }
}