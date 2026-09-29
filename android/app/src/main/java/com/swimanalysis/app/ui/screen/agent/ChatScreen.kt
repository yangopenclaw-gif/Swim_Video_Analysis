package com.swimanalysis.app.ui.screen.agent

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AddComment
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import com.swimanalysis.app.data.model.ConversationDto
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
    var inputText by remember { mutableStateOf("") }

    val voiceLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val text = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
            if (!text.isNullOrBlank()) {
                inputText = text
            }
        }
    }

    val imageLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) viewModel.extractImage(uri)
    }

    val docLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) viewModel.parseDocument(uri)
    }

    fun launchVoice() {
        if (state.isSending) return
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "说出要告诉小咩的话")
        }
        voiceLauncher.launch(intent)
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

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("小咩助手") },
                actions = {
                    IconButton(onClick = { viewModel.toggleHistory(true) }) {
                        Icon(Icons.Filled.History, contentDescription = "历史会话")
                    }
                    IconButton(onClick = { viewModel.newConversation() }) {
                        Icon(Icons.Filled.AddComment, contentDescription = "新对话")
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
                text = inputText,
                isSending = state.isSending,
                statusText = state.statusText,
                onTextChange = { inputText = it },
                onSend = {
                    viewModel.send(inputText)
                    inputText = ""
                },
                onMic = { launchVoice() },
                onImage = { imageLauncher.launch("image/*") },
                onDoc = { docLauncher.launch(arrayOf(
                    "application/pdf",
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "text/plain"
                )) },
                onStopStreaming = { viewModel.stopStreaming() }
            )
        }
    }

    if (state.showHistory) {
        HistoryDialog(
            conversations = state.conversations,
            onSelect = viewModel::switchConversation,
            onDelete = viewModel::deleteConversation,
            onDismiss = { viewModel.toggleHistory(false) }
        )
    }

    if (state.imageExtracting || state.extractedText.isNotBlank() || state.imageError != null) {
        ImageExtractDialog(
            extracting = state.imageExtracting,
            title = state.extractedTitle,
            text = state.extractedText,
            error = state.imageError,
            onTitleChange = viewModel::setExtractedTitle,
            onTextChange = viewModel::setExtractedText,
            onSave = viewModel::saveExtractedToKb,
            onDismiss = viewModel::dismissImageResult
        )
    }

    if (state.docParsing || state.docText.isNotBlank() || state.docError != null) {
        DocParseDialog(
            parsing = state.docParsing,
            filename = state.docFilename,
            text = state.docText,
            error = state.docError,
            onTextChange = viewModel::setDocText,
            onSave = viewModel::saveDocToKb,
            onDismiss = viewModel::dismissDocResult
        )
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
                Text("咩", color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.headlineSmall)
            }
            Spacer(Modifier.height(12.dp))
            Text("我是你的专属智能体小咩", style = MaterialTheme.typography.titleMedium)
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
            SelectionContainer {
                Text(
                    msg.content,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (isUser) Color.White else MaterialTheme.colorScheme.onSurface
                )
            }
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
            SelectionContainer {
                Text(text, style = MaterialTheme.typography.bodyMedium)
            }
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
        Text("咩", color = Color.White, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun InputBar(
    text: String,
    isSending: Boolean,
    statusText: String,
    onTextChange: (String) -> Unit,
    onSend: () -> Unit,
    onMic: () -> Unit,
    onImage: () -> Unit,
    onDoc: () -> Unit,
    onStopStreaming: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .imePadding()
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
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = text,
                onValueChange = onTextChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("输入或语音告诉我") },
                maxLines = 3,
                shape = RoundedCornerShape(24.dp)
            )
            Spacer(Modifier.width(8.dp))
            IconButton(
                onClick = onImage,
                modifier = Modifier.size(44.dp)
            ) {
                Icon(Icons.Filled.AddPhotoAlternate, contentDescription = "上传图片识别入库", tint = WarmCoral)
            }
            IconButton(
                onClick = onDoc,
                modifier = Modifier.size(44.dp)
            ) {
                Icon(Icons.Filled.Description, contentDescription = "上传文档解析", tint = WarmCoral)
            }
            Spacer(Modifier.width(4.dp))
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
                IconButton(
                    onClick = onMic,
                    modifier = Modifier
                        .size(44.dp)
                        .clip(CircleShape)
                        .background(WarmCoral)
                ) {
                    Icon(Icons.Filled.Mic, contentDescription = "语音输入", tint = Color.White)
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

@Composable
private fun HistoryDialog(
    conversations: List<ConversationDto>,
    onSelect: (String) -> Unit,
    onDelete: (String) -> Unit,
    onDismiss: () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(20.dp)) {
                Text("历史会话", style = MaterialTheme.typography.titleLarge)
                Spacer(Modifier.height(12.dp))
                if (conversations.isEmpty()) {
                    Text(
                        "暂无历史会话",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    LazyColumn(
                        modifier = Modifier.height(360.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(conversations, key = { it.id }) { conv ->
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                                ),
                                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { onSelect(conv.id) }
                                        .padding(horizontal = 12.dp, vertical = 10.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Column(Modifier.weight(1f)) {
                                        Text(
                                            conv.title.ifBlank { "新对话" },
                                            style = MaterialTheme.typography.bodyMedium,
                                            maxLines = 1
                                        )
                                        if (conv.updatedAt != null) {
                                            Text(
                                                conv.updatedAt,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                        }
                                    }
                                    IconButton(
                                        onClick = { onDelete(conv.id) },
                                        modifier = Modifier.size(32.dp)
                                    ) {
                                        Icon(
                                            Icons.Filled.Delete,
                                            contentDescription = "删除会话",
                                            tint = MaterialTheme.colorScheme.error,
                                            modifier = Modifier.size(18.dp)
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
            }
        }
    }
}

@Composable
private fun DocParseDialog(
    parsing: Boolean,
    filename: String,
    text: String,
    error: String?,
    onTextChange: (String) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(20.dp)) {
                Text("文档解析", style = MaterialTheme.typography.titleLarge)
                Text(
                    if (filename.isBlank()) "已从文档中提取文字，可编辑后加入知识库。"
                    else "已解析「$filename」，可编辑后加入知识库。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(12.dp))

                if (parsing) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 3.dp)
                        Spacer(Modifier.width(10.dp))
                        Text("正在解析文档…", style = MaterialTheme.typography.bodyMedium)
                    }
                    Spacer(Modifier.height(16.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = onDismiss) { Text("取消") }
                    }
                } else {
                    OutlinedTextField(
                        value = text,
                        onValueChange = onTextChange,
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("解析出的文字") },
                        minLines = 5,
                        maxLines = 10
                    )
                    error?.let {
                        Spacer(Modifier.height(4.dp))
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = onDismiss) { Text("取消") }
                        Spacer(Modifier.width(8.dp))
                        TextButton(onClick = onSave) { Text("添加到知识库") }
                    }
                }
            }
        }
    }
}


@Composable
private fun ImageExtractDialog(
    extracting: Boolean,
    title: String,
    text: String,
    error: String?,
    onTitleChange: (String) -> Unit,
    onTextChange: (String) -> Unit,
    onSave: () -> Unit,
    onDismiss: () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(20.dp)) {
                Text("图片转知识", style = MaterialTheme.typography.titleLarge)
                Text(
                    "已从图片中提炼信息，可编辑后加入知识库。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(12.dp))

                if (extracting) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 3.dp)
                        Spacer(Modifier.width(10.dp))
                        Text("正在识别图片…", style = MaterialTheme.typography.bodyMedium)
                    }
                    Spacer(Modifier.height(16.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = onDismiss) { Text("取消") }
                    }
                } else {
                    OutlinedTextField(
                        value = title,
                        onValueChange = onTitleChange,
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("标题（可选）") },
                        singleLine = true
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = text,
                        onValueChange = onTextChange,
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("抽取的内容") },
                        minLines = 4,
                        maxLines = 8
                    )
                    error?.let {
                        Spacer(Modifier.height(4.dp))
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = onDismiss) { Text("取消") }
                        Spacer(Modifier.width(8.dp))
                        TextButton(onClick = onSave) { Text("添加到知识库") }
                    }
                }
            }
        }
    }
}