package com.swimanalysis.app.ui.screen

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.swimanalysis.app.media.VideoPicker
import com.swimanalysis.app.ui.navigation.Screen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(navController: NavController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("泳娃分析") },
                actions = {
                    IconButton(onClick = { navController.navigate(Screen.Settings.route) }) {
                        Icon(Icons.Filled.Settings, contentDescription = "设置")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "游泳比赛视频分析系统",
                style = MaterialTheme.typography.headlineMedium,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = "请通过底部导航访问各功能模块",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecordsScreen(navController: NavController, viewModel: RecordsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    var pendingAvatarName by remember { mutableStateOf<String?>(null) }
    var pendingCropUri by remember { mutableStateOf<Uri?>(null) }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) pendingCropUri = uri
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("比赛记录") },
                actions = {
                    IconButton(onClick = { viewModel.loadRecords() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (state.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        Text(
                            text = "选择泳者查看个人记录",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    items(RecordsViewModel.PERSONS) { name ->
                        SwimmerCard(
                            name = name,
                            avatarPath = state.avatarPaths[name],
                            recordCount = state.records.count { it.swimmerName == name },
                            onClick = { navController.navigate(Screen.SwimmerRecords.withArgs(name)) },
                            onEditAvatar = {
                                pendingAvatarName = name
                                galleryLauncher.launch("image/*")
                            }
                        )
                    }
                }
            }

            state.error?.let {
                Text(
                    text = "加载失败: $it",
                    modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp),
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }

    pendingCropUri?.let { uri ->
        val name = pendingAvatarName
        if (name != null) {
            AvatarCropDialog(
                imageUri = uri,
                onConfirm = { bitmap ->
                    viewModel.saveAvatarBitmap(name, bitmap)
                    pendingCropUri = null
                    pendingAvatarName = null
                },
                onDismiss = {
                    pendingCropUri = null
                    pendingAvatarName = null
                }
            )
        }
    }
}

@Composable
private fun SwimmerCard(
    name: String,
    avatarPath: String?,
    recordCount: Int,
    onClick: () -> Unit,
    onEditAvatar: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .clickable { onEditAvatar() }
            ) {
                val hasAvatar = !avatarPath.isNullOrEmpty() && java.io.File(avatarPath).exists()
                if (hasAvatar) {
                    AsyncImage(
                        model = java.io.File(avatarPath),
                        contentDescription = "$name 的头像",
                        modifier = Modifier.fillMaxSize()
                    )
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(MaterialTheme.colorScheme.primaryContainer),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            Icons.Filled.Person,
                            contentDescription = "点击设置头像",
                            modifier = Modifier.size(36.dp),
                            tint = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.size(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(name, style = MaterialTheme.typography.titleLarge)
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "$recordCount 条记录",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(
                Icons.Filled.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SwimmerRecordsScreen(
    navController: NavController,
    swimmerName: String,
    viewModel: RecordsViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    var showAddDialog by remember { mutableStateOf(false) }
    val swimmerRecords = state.records.filter { it.swimmerName == swimmerName }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("$swimmerName 的记录") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadRecords() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                    }
                }
            )
        },
        floatingActionButton = {
            androidx.compose.material3.ExtendedFloatingActionButton(
                onClick = { showAddDialog = true },
                icon = { Icon(Icons.Filled.Add, contentDescription = "添加") },
                text = { Text("添加记录") }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (state.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else if (swimmerRecords.isEmpty()) {
                Column(
                    modifier = Modifier.align(Alignment.Center),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text("暂无记录", style = MaterialTheme.typography.bodyLarge)
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("点击右下角\"添加记录\"手动录入",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(
                        start = 16.dp, end = 16.dp, top = 16.dp, bottom = 96.dp
                    ),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(swimmerRecords) { record ->
                        RecordCard(
                            record = record,
                            onClick = {
                                navController.navigate(Screen.RecordDetail.withArgs(record.id))
                            }
                        )
                    }
                }
            }

            state.error?.let {
                Text(
                    text = "加载失败: $it",
                    modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp),
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
    }

    if (showAddDialog) {
        ManualRecordDialog(
            defaultName = swimmerName,
            onDismiss = { showAddDialog = false },
            onConfirm = { name, distance, stroke, raceName, date, location, time ->
                viewModel.addManualRecord(name, 50, distance, stroke, raceName, date, location, time)
                showAddDialog = false
            }
        )
    }

    if (state.addSuccess) {
        androidx.compose.material3.Snackbar(
            modifier = Modifier.padding(16.dp),
            action = {
                androidx.compose.material3.TextButton(onClick = { viewModel.clearAddSuccess() }) {
                    Text("确定")
                }
            }
        ) { Text("记录添加成功") }
    }
}

@Composable
private fun RecordCard(
    record: com.swimanalysis.app.data.model.RecordDto,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = record.swimmerName,
                style = MaterialTheme.typography.titleMedium
            )
            Text(
                text = "${record.raceDistance}米${record.strokeType}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            record.raceName?.takeIf { it.isNotEmpty() }?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                record.raceDate?.takeIf { it.isNotEmpty() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                record.analysisResult?.let { ar ->
                    val totalTime = extractTotalTime(ar)
                    totalTime?.let {
                        Text(it, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Medium)
                    }
                }
            }
        }
    }
}

private fun extractTotalTime(jsonElement: kotlinx.serialization.json.JsonElement): String? {
    val raw = try {
        val obj = jsonElement as? kotlinx.serialization.json.JsonObject ?: return null
        obj["比赛总用时"]?.let { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }
            ?: obj["total_time"]?.let { (it as? kotlinx.serialization.json.JsonPrimitive)?.content }
    } catch (e: Exception) { null } ?: return null
    return formatTotalTime(raw)
}

private val TIME_KEYS = setOf(
    "比赛总用时", "总用时", "total_time",
    "第1半程用时", "第2半程用时", "前程用时", "后程用时",
    "转身出水用时", "转身用时"
)

fun formatTotalTime(raw: String): String? {
    val seconds = parseSeconds(raw) ?: return raw
    val minutes = (seconds / 60).toInt()
    val sec = seconds % 60
    return if (minutes > 0) {
        val secStr = "%.2f".format(sec).let { if (sec < 10) "0$it" else it }
        "${minutes}分${secStr}秒"
    } else {
        "%.2f秒".format(sec)
    }
}

private fun parseSeconds(raw: String): Double? {
    val trimmed = raw.trim()
    if (trimmed.contains("分")) {
        val parts = trimmed.split("分")
        val m = parts.getOrNull(0)?.toDoubleOrNull() ?: return null
        val sPart = parts.getOrNull(1)?.removeSuffix("秒")?.trim() ?: "0"
        val s = sPart.toDoubleOrNull() ?: return null
        return m * 60 + s
    }
    if (trimmed.contains(":")) {
        val parts = trimmed.split(":")
        val m = parts.getOrNull(0)?.toDoubleOrNull() ?: return null
        val s = parts.getOrNull(1)?.toDoubleOrNull() ?: return null
        return m * 60 + s
    }
    return trimmed.toDoubleOrNull()
}

@Composable
private fun ManualRecordDialog(
    onDismiss: () -> Unit,
    onConfirm: (String, Int, String, String, String, String, String) -> Unit,
    defaultName: String = "杨钧涵",
    viewModel: RecordsViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val state by viewModel.state.collectAsState()
    var swimmerName by remember { mutableStateOf(defaultName) }
    var distance by remember { mutableStateOf("50") }
    var stroke by remember { mutableStateOf("自由泳") }
    var raceName by remember { mutableStateOf("") }
    var raceDate by remember { mutableStateOf("") }
    var raceLocation by remember { mutableStateOf("") }
    var totalTime by remember { mutableStateOf("") }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            VideoPicker.uriToFile(context, uri)?.let { viewModel.recognizeImage(it) }
        }
    }

    LaunchedEffect(state.recognizeResult) {
        val result = state.recognizeResult ?: return@LaunchedEffect
        val data = result["data"] as? Map<*, *> ?: return@LaunchedEffect
        fun s(k: String): String = data[k]?.toString()?.takeIf { it.isNotBlank() } ?: ""
        s("race_distance").let { if (it.isNotEmpty()) distance = it }
        s("stroke_type").let { if (it.isNotEmpty()) stroke = it }
        s("race_name").let { if (it.isNotEmpty()) raceName = it }
        s("race_date").let { if (it.isNotEmpty()) raceDate = it }
        s("race_location").let { if (it.isNotEmpty()) raceLocation = it }
        s("比赛总用时").let { if (it.isNotEmpty()) totalTime = it }
        viewModel.clearRecognize()
    }

    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加比赛记录") },
        text = {
            Column(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.verticalScroll(rememberScrollState())
            ) {
                androidx.compose.material3.OutlinedTextField(
                    value = swimmerName, onValueChange = { swimmerName = it },
                    label = { Text("泳者姓名") }, modifier = Modifier.fillMaxWidth()
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    androidx.compose.material3.OutlinedTextField(
                        value = distance, onValueChange = { distance = it },
                        label = { Text("距离(米)") }, modifier = Modifier.weight(1f)
                    )
                    androidx.compose.material3.OutlinedTextField(
                        value = stroke, onValueChange = { stroke = it },
                        label = { Text("泳姿") }, modifier = Modifier.weight(1f)
                    )
                }
                androidx.compose.material3.OutlinedTextField(
                    value = raceName, onValueChange = { raceName = it },
                    label = { Text("比赛名称") }, modifier = Modifier.fillMaxWidth()
                )
                androidx.compose.material3.OutlinedTextField(
                    value = raceDate, onValueChange = { raceDate = it },
                    label = { Text("比赛日期") }, modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("如 2025-06-15") }
                )
                androidx.compose.material3.OutlinedTextField(
                    value = raceLocation, onValueChange = { raceLocation = it },
                    label = { Text("比赛地点") }, modifier = Modifier.fillMaxWidth()
                )
                androidx.compose.material3.OutlinedTextField(
                    value = totalTime, onValueChange = { totalTime = it },
                    label = { Text("总成绩") }, modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("如 1:05.23 或 65.23 秒") }
                )

                Spacer(modifier = Modifier.height(4.dp))
                androidx.compose.material3.OutlinedButton(
                    onClick = { galleryLauncher.launch("image/*") },
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !state.recognizeLoading
                ) {
                    if (state.recognizeLoading) {
                        androidx.compose.material3.CircularProgressIndicator(
                            modifier = Modifier.size(16.dp), strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.size(8.dp))
                    } else {
                        Icon(Icons.Filled.PhotoLibrary, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.size(8.dp))
                    }
                    Text(if (state.recognizeLoading) "AI识别中..." else "AI识别成绩单自动填充")
                }
                state.recognizeError?.let {
                    Text(
                        text = "识别失败: $it",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
                if (state.recognizeResult != null) {
                    Text(
                        text = "已识别并填充，请核对后点击添加",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
        },
        confirmButton = {
            androidx.compose.material3.TextButton(
                onClick = {
                    onConfirm(swimmerName, distance.toIntOrNull() ?: 50, stroke,
                        raceName, raceDate, raceLocation, totalTime)
                },
                enabled = swimmerName.isNotEmpty() && totalTime.isNotEmpty()
            ) { Text("添加") }
        },
        dismissButton = {
            androidx.compose.material3.TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UploadScreen(navController: NavController, viewModel: UploadViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = { TopAppBar(title = { Text("上传视频") }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("视频上传功能", style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "选择或拍摄视频后将自动分片上传",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(24.dp))
            if (state.isUploading) {
                CircularProgressIndicator(progress = state.uploadProgress)
                Spacer(modifier = Modifier.height(8.dp))
                Text(state.uploadMessage)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VideosScreen(navController: NavController, viewModel: VideosViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = { TopAppBar(title = { Text("视频库") }) }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (state.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.videos) { video ->
                        Card(
                            modifier = Modifier.fillMaxSize(),
                            onClick = {
                                navController.navigate(Screen.VideoPlayer.withArgs(video.id))
                            },
                            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text(
                                    text = video.displayName.ifEmpty { video.fileName },
                                    style = MaterialTheme.typography.titleMedium
                                )
                                video.athleteName.let {
                                    if (it.isNotEmpty()) {
                                        Text(
                                            text = it,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(navController: NavController) {
    Scaffold(
        topBar = { TopAppBar(title = { Text("我的") }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            Text("个人中心", style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "泳者档案、设置等功能",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecordDetailScreen(navController: NavController, recordId: String, viewModel: RecordsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    val record = state.records.find { it.id == recordId }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("记录详情") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (record == null) {
                Text(
                    text = if (state.isLoading) "加载中..." else "未找到记录",
                    modifier = Modifier.align(Alignment.Center),
                    style = MaterialTheme.typography.bodyLarge
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    item {
                        Card(modifier = Modifier.fillMaxWidth(), elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text(record.swimmerName, style = MaterialTheme.typography.titleLarge)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("${record.raceDistance}米${record.strokeType}",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = MaterialTheme.colorScheme.primary)
                                record.raceName?.takeIf { it.isNotEmpty() }?.let {
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text("比赛: $it", style = MaterialTheme.typography.bodyMedium)
                                }
                                record.raceDate?.takeIf { it.isNotEmpty() }?.let {
                                    Text("日期: $it", style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                                record.raceLocation?.takeIf { it.isNotEmpty() }?.let {
                                    Text("地点: $it", style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                    record.analysisResult?.let { ar ->
                        item {
                            Card(modifier = Modifier.fillMaxWidth(), elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Text("分析结果", style = MaterialTheme.typography.titleMedium)
                                    Spacer(modifier = Modifier.height(8.dp))
                                    val obj = ar as? kotlinx.serialization.json.JsonObject
                                    obj?.forEach { (key, value) ->
                                        val rawValue = (value as? kotlinx.serialization.json.JsonPrimitive)?.content ?: value.toString()
                                        val displayValue = if (key in TIME_KEYS) {
                                            formatTotalTime(rawValue) ?: rawValue
                                        } else {
                                            rawValue
                                        }
                                        Row(modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.SpaceBetween) {
                                            Text(key, style = MaterialTheme.typography.bodyMedium,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            Text(displayValue,
                                                style = MaterialTheme.typography.bodyMedium)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VideoPlayerScreen(navController: NavController, videoId: String) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("视频播放") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text(
                text = "视频ID: $videoId",
                modifier = Modifier.align(Alignment.Center)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VideoAnnotateScreen(navController: NavController, videoId: String) {
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
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text(
                text = "标注视频: $videoId",
                modifier = Modifier.align(Alignment.Center)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AnalyzeProgressScreen(navController: NavController, taskId: String) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("分析进度") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text(
                text = "任务ID: $taskId",
                modifier = Modifier.align(Alignment.Center)
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompareScreen(navController: NavController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("记录对比") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text("记录对比", modifier = Modifier.align(Alignment.Center))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompetitionsScreen(navController: NavController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("比赛管理") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text("比赛管理", modifier = Modifier.align(Alignment.Center))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AiRecognizeScreen(navController: NavController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AI识别") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Text("AI识别成绩单", modifier = Modifier.align(Alignment.Center))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(navController: NavController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("设置") },
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
                .padding(16.dp)
        ) {
            Text("设置", style = MaterialTheme.typography.titleLarge)
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "服务器地址、缓存清理等",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}