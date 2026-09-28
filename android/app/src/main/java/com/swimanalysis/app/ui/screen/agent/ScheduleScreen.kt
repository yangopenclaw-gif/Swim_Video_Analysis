package com.swimanalysis.app.ui.screen.agent

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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.swimanalysis.app.data.model.ScheduleDto
import com.swimanalysis.app.ui.theme.WarmCoral
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScheduleScreen(viewModel: ScheduleViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsState()
    var viewMode by remember { mutableStateOf(0) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("提醒") }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            TabRow(selectedTabIndex = viewMode) {
                Tab(selected = viewMode == 0, onClick = { viewMode = 0 }, text = { Text("列表") })
                Tab(selected = viewMode == 1, onClick = { viewMode = 1 }, text = { Text("日历") })
            }
            when (viewMode) {
                0 -> ScheduleListView(state, viewModel::delete)
                1 -> ScheduleCalendarView(state, viewModel::delete)
            }
        }
    }
}

@Composable
private fun ScheduleListView(state: ScheduleUiState, onDelete: (String) -> Unit) {
    if (state.loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        return
    }
    if (state.schedules.isEmpty()) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("还没有提醒", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(4.dp))
                Text(
                    "对助手说「提醒我…」即可添加",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        return
    }
    LazyColumn(
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        items(state.schedules, key = { it.id }) { s ->
            ScheduleCard(s, onDelete)
        }
    }
}

@Composable
private fun ScheduleCard(s: ScheduleDto, onDelete: (String) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Text(s.title, style = MaterialTheme.typography.titleSmall)
                if (s.content.isNotBlank()) {
                    Text(
                        s.content,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(Modifier.height(4.dp))
                Text(formatScheduleMeta(s), style = MaterialTheme.typography.bodySmall, color = WarmCoral)
            }
            IconButton(onClick = { onDelete(s.id) }, modifier = Modifier.size(36.dp)) {
                Icon(
                    Icons.Filled.Delete,
                    contentDescription = "删除",
                    tint = MaterialTheme.colorScheme.error,
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}

private fun formatScheduleMeta(s: ScheduleDto): String {
    val repeat = when (s.repeat) {
        "daily" -> "每天"
        "weekly" -> "每周"
        else -> "单次"
    }
    return "${s.remindAt} · $repeat"
}

@Composable
private fun ScheduleCalendarView(state: ScheduleUiState, onDelete: (String) -> Unit) {
    var currentMonth by remember { mutableStateOf(YearMonth.now()) }
    var selectedDate by remember { mutableStateOf<LocalDate?>(null) }

    val byDate = remember(state.schedules) {
        state.schedules.groupBy { it.remindAt.substringBefore(' ') }
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { currentMonth = currentMonth.minusMonths(1) }) {
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "上月")
            }
            Text(
                "${currentMonth.year}年${currentMonth.monthValue}月",
                modifier = Modifier.weight(1f),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.titleMedium
            )
            IconButton(onClick = { currentMonth = currentMonth.plusMonths(1) }) {
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "下月")
            }
        }

        Row(Modifier.fillMaxWidth()) {
            listOf("一", "二", "三", "四", "五", "六", "日").forEach { label ->
                Text(
                    label,
                    modifier = Modifier.weight(1f),
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        val first = currentMonth.atDay(1)
        val offset = first.dayOfWeek.value - 1
        val days = currentMonth.lengthOfMonth()
        val totalCells = ((offset + days + 6) / 7) * 7
        Column(Modifier.padding(horizontal = 8.dp, vertical = 4.dp)) {
            var cell = 0
            while (cell < totalCells) {
                Row(Modifier.fillMaxWidth()) {
                    repeat(7) { col ->
                        val index = cell + col
                        val dayNum = index - offset + 1
                        val date = if (dayNum in 1..days) currentMonth.atDay(dayNum) else null
                        DayCell(
                            date = date,
                            isSelected = date != null && date == selectedDate,
                            hasSchedule = date != null && byDate.containsKey(date.format(DateTimeFormatter.ISO_LOCAL_DATE)),
                            onClick = { if (date != null) selectedDate = date },
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
                cell += 7
            }
        }

        selectedDate?.let { d ->
            val items = byDate[d.format(DateTimeFormatter.ISO_LOCAL_DATE)] ?: emptyList()
            Text(
                "${d.monthValue}月${d.dayOfMonth}日 的提醒",
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                style = MaterialTheme.typography.titleSmall
            )
            if (items.isEmpty()) {
                Text(
                    "当天无提醒",
                    modifier = Modifier.padding(horizontal = 16.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                LazyColumn(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(items, key = { it.id }) { s ->
                        ScheduleCard(s, onDelete)
                    }
                }
            }
        }
    }
}

@Composable
private fun DayCell(
    date: LocalDate?,
    isSelected: Boolean,
    hasSchedule: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    if (date == null) {
        Box(modifier.height(44.dp))
        return
    }
    val bg = if (isSelected) WarmCoral else Color.Transparent
    Box(
        modifier = modifier
            .height(44.dp)
            .padding(2.dp)
            .clip(CircleShape)
            .background(bg)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                date.dayOfMonth.toString(),
                color = if (isSelected) Color.White else MaterialTheme.colorScheme.onSurface,
                style = MaterialTheme.typography.bodyMedium
            )
            if (hasSchedule) {
                Box(
                    Modifier
                        .size(4.dp)
                        .clip(CircleShape)
                        .background(if (isSelected) Color.White else WarmCoral)
                )
            }
        }
    }
}