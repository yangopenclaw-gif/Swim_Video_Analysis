package com.swimanalysis.app.ui.screen.agent

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.VolumeOff
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.swimanalysis.app.ui.theme.WarmCoral
import com.swimanalysis.app.ui.theme.WarmPeach

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    navController: NavController,
    viewModel: ChatViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val context = LocalContext.current
    var partialText by remember { mutableStateOf("") }
    var showKbDialog by remember { mutableStateOf(false) }
    var listeningLevel by remember { mutableStateOf(0f) }
    var voiceError by remember { mutableStateOf<String?>(null) }

    var hasRecordPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasRecordPermission = granted }

    val voiceHelper = remember {
        VoiceHelper(
            context = context,
            onPartialResult = { partialText = it },
            onFinalResult = { text ->
                partialText = ""
                voiceError = null
                viewModel.send(text)
            },
            onError = { voiceError = it },
            onRms = { listeningLevel = it }
        )
    }
    DisposableEffect(Unit) {
        onDispose { voiceHelper.shutdown() }
    }

    val notificationLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { }
    LaunchedEffect(Unit) {
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    val listState = rememberLazyListState()
    val itemCount = state.messages.size + if (state.streamingText.isNotBlank()) 1 else 0
    LaunchedEffect(itemCount) {
        if (itemCount > 0) listState.animateScrollToItem(itemCount - 1)
    }

    LaunchedEffect(state.messages.size, state.isSending) {
        val last = state.messages.lastOrNull { it.role == "assistant" }?.content
        if (!state.isSending && last != null && state.autoSpeak && last != state.spokenAssistantContent) {
            viewModel.markSpoken(last)
            voiceHelper.speak(last)
        }
    }

    fun startVoice() {
        if (state.isSending) return
        voiceError = null
        if (hasRecordPermission) {
            viewModel.setListening(true)
            voiceHelper.startListening()
        } else {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    fun stopVoice() {
        viewModel.setListening(false)
        voiceHelper.stopListening()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("小账助手") },
                actions = {
                    IconButton(onClick = { viewModel.toggleAutoSpeak() }) {
                        Icon(
                            if (state.autoSpeak) Icons.Filled.VolumeUp else Icons.Filled.VolumeOff,
                            contentDescription = "语音播报开关"
                        )
                    }
                    IconButton(onClick = { showKbDialog = true }) {
                        Icon(Icons.Filled.Folder, contentDescription = "知识库")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            QuickActions(
                onAction = { viewModel.send(it) },
                enabled = !state.isSending
            )

            if (state.messages.isEmpty() && state.streamingText.isBlank() && !state.isSending) {
                EmptyState(Modifier.weight(1f))
            } else {
                LazyColumn(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    state = listState,
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(state.messages) { msg ->
                        MessageBubble(msg)
                    }
                    if (state.streamingText.isNotBlank()) {
                        item { StreamingBubble(state.streamingText) }
                    }
                }
            }

            InputBar(
                text = partialText,
                isSending = state.isSending,
                listening = state.listening,
                listeningLevel = listeningLevel,
                statusText = state.statusText,
                errorText = voiceError,
                onTextChange = { partialText = it },
                onSend = {
                    viewModel.send(partialText)
                    partialText = ""
                },
                onMicDown = { startVoice() },
                onMicUp = { stopVoice() },
                onStopStreaming = { viewModel.stopStreaming() }
            )
        }
    }

    if (showKbDialog) {
        KbManagerDialog(onDismiss = { showKbDialog = false })
    }
}

@Composable
private fun QuickActions(onAction: (String) -> Unit, enabled: Boolean) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        listOf("记一笔", "查账单", "本月统计", "提醒我").forEach { label ->
            SuggestionChip(
                onClick = { onAction(label) },
                enabled = enabled,
                label = { Text(label, style = MaterialTheme.typography.bodySmall) }
            )
        }
    }
}

@Composable
private fun EmptyState(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier.fillMaxWidth(),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(Brush.linearGradient(listOf(WarmCoral, WarmPeach))),
                contentAlignment = Alignment.Center
            ) {
                Text("账", color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.headlineSmall)
            }
            Spacer(Modifier.height(12.dp))
            Text("我是你的专属智能体小账", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(4.dp))
            Text(
                "试试说：记一笔午饭30块、提醒我明天开会、本月花了多少",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun MessageBubble(msg: ChatUiMessage) {
    val isUser = msg.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        if (!isUser) {
            AssistantAvatar()
            Spacer(Modifier.width(8.dp))
        }
        Box(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .clip(
                    RoundedCornerShape(
                        topStart = 16.dp,
                        topEnd = 16.dp,
                        bottomStart = if (isUser) 16.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 16.dp
                    )
                )
                .background(
                    if (isUser) Brush.horizontalGradient(listOf(WarmCoral, WarmPeach))
                    else Brush.horizontalGradient(listOf(Color.White, Color(0xFFFFF3EA)))
                )
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(
                msg.content,
                style = MaterialTheme.typography.bodyMedium,
                color = if (isUser) Color.White else MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
private fun StreamingBubble(text: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        AssistantAvatar()
        Spacer(Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .clip(RoundedCornerShape(16.dp, 16.dp, 16.dp, 4.dp))
                .background(Brush.horizontalGradient(listOf(Color.White, Color(0xFFFFF3EA))))
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(text, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun AssistantAvatar() {
    Box(
        modifier = Modifier
            .size(32.dp)
            .clip(CircleShape)
            .background(Brush.linearGradient(listOf(WarmCoral, WarmPeach))),
        contentAlignment = Alignment.Center
    ) {
        Text("账", color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun InputBar(
    text: String,
    isSending: Boolean,
    listening: Boolean,
    listeningLevel: Float,
    statusText: String,
    errorText: String?,
    onTextChange: (String) -> Unit,
    onSend: () -> Unit,
    onMicDown: () -> Unit,
    onMicUp: () -> Unit,
    onStopStreaming: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .padding(horizontal = 12.dp, vertical = 8.dp)
    ) {
        if (statusText.isNotBlank()) {
            Row(
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                CircularProgressIndicator(modifier = Modifier.size(12.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(6.dp))
                Text(statusText, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if (errorText != null) {
            Text(
                errorText,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
            )
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = text,
                onValueChange = onTextChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text(if (listening) "正在聆听…" else "输入或语音告诉我") },
                maxLines = 3,
                shape = RoundedCornerShape(24.dp)
            )
            Spacer(Modifier.width(8.dp))
            if (isSending) {
                IconButton(
                    onClick = onStopStreaming,
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(WarmCoral)
                ) {
                    Icon(Icons.Filled.Stop, contentDescription = "停止", tint = Color.White)
                }
            } else if (text.isBlank()) {
                Box(
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(if (listening) WarmCoral else MaterialTheme.colorScheme.surfaceVariant)
                        .graphicsLayer {
                            val s = if (listening) 1f + (listeningLevel / 20f).coerceIn(0f, 0.25f) else 1f
                            scaleX = s
                            scaleY = s
                        }
                        .pointerInput(Unit) {
                            detectTapGestures(
                                onPress = {
                                    onMicDown()
                                    tryAwaitRelease()
                                    onMicUp()
                                }
                            )
                        },
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Filled.Mic, contentDescription = "按住说话", tint = if (listening) Color.White else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                IconButton(
                    onClick = onSend,
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(WarmCoral)
                ) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "发送", tint = Color.White)
                }
            }
        }
    }
}