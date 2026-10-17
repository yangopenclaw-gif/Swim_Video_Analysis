package com.swimanalysis.app.ui.screen.ledger

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.ViewList
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.navigation.NavController
import com.swimanalysis.app.data.model.AmountItemDto
import com.swimanalysis.app.data.model.CalendarDayDto
import com.swimanalysis.app.data.model.CategoryStat
import com.swimanalysis.app.data.model.LedgerEntryDto
import com.swimanalysis.app.ui.theme.ExpenseRed
import com.swimanalysis.app.ui.theme.IncomeGreen
import com.swimanalysis.app.ui.theme.WarmCoral
import com.swimanalysis.app.ui.theme.WarmPeach
import java.time.YearMonth


private fun formatAmount(value: Double): String {
    return if (value == value.toLong().toDouble()) {
        value.toLong().toString()
    } else {
        String.format("%.2f", value)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LedgerScreen(
    navController: NavController,
    ledgerViewModel: LedgerViewModel = hiltViewModel(),
    statsViewModel: StatsViewModel = hiltViewModel()
) {
    val state by ledgerViewModel.state.collectAsState()
    val statsState by statsViewModel.state.collectAsState()
    val passwordCheck by ledgerViewModel.passwordCheck.collectAsState()
    var pendingEdit by remember { mutableStateOf<LedgerEntryDto?>(null) }
    var pendingDelete by remember { mutableStateOf<LedgerEntryDto?>(null) }
    var passwordInput by remember { mutableStateOf("") }
    var selectedDate by remember { mutableStateOf<String?>(null) }
    var tab by remember { mutableStateOf(0) }

    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                ledgerViewModel.load()
                statsViewModel.load()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("账单") })
        },
        floatingActionButton = {
            FloatingActionButton(onClick = { navController.navigate("add_entry") }) {
                Icon(Icons.Filled.Add, contentDescription = "记一笔")
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            TabRow(selectedTabIndex = tab) {
                Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("明细") })
                Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("统计") })
            }
            when (tab) {
                0 -> LedgerDetailView(
                    state = state,
                    viewModel = ledgerViewModel,
                    onDayClick = { selectedDate = it },
                    onDelete = {
                        pendingEdit = null
                        pendingDelete = it
                        passwordInput = ""
                        ledgerViewModel.clearPasswordError()
                    },
                    onEdit = {
                        pendingDelete = null
                        pendingEdit = it
                        passwordInput = ""
                        ledgerViewModel.clearPasswordError()
                    }
                )
                1 -> StatsDetailView(state = statsState, viewModel = statsViewModel)
            }
        }
    }

    selectedDate?.let { date ->
        val dayEntries = state.entries.filter { it.entryDate == date }
        AlertDialog(
            onDismissRequest = { selectedDate = null },
            title = { Text("$date 明细") },
            text = {
                if (dayEntries.isEmpty()) {
                    Text("当天无记录", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        dayEntries.forEach { e ->
                            val isExpense = e.entryType != "income"
                            val amt = if (e.amounts.isNotEmpty()) e.amounts.first().amount else e.amount
                            val unit = if (e.currency == "CNY") "元" else LedgerCurrencies.name(e.currency)
                            Text(
                                "${e.category} ${if (isExpense) "-" else "+"}${formatAmount(amt)} $unit${if (e.note.isNotBlank()) " · ${e.note}" else ""}",
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }
            },
            confirmButton = { TextButton(onClick = { selectedDate = null }) { Text("关闭") } }
        )
    }

    if (pendingEdit != null || pendingDelete != null) {
        val editing = pendingEdit != null
        AlertDialog(
            onDismissRequest = {
                pendingEdit = null
                pendingDelete = null
                ledgerViewModel.clearPasswordError()
            },
            title = { Text(if (editing) "验证身份" else "删除验证") },
            text = {
                Column {
                    Text(
                        if (editing) "修改记录前请输入登录密码" else "删除记录前请输入登录密码",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = passwordInput,
                        onValueChange = {
                            passwordInput = it
                            if (passwordCheck.error != null) ledgerViewModel.clearPasswordError()
                        },
                        label = { Text("密码") },
                        singleLine = true,
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth()
                    )
                    passwordCheck.error?.let {
                        Spacer(Modifier.height(8.dp))
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val entry = pendingEdit ?: pendingDelete ?: return@TextButton
                        ledgerViewModel.verifyPassword(passwordInput) {
                            pendingEdit = null
                            pendingDelete = null
                            passwordInput = ""
                            if (editing) {
                                navController.navigate("add_entry?entryId=${entry.id}")
                            } else {
                                ledgerViewModel.deleteEntry(entry.id)
                            }
                        }
                    },
                    enabled = passwordInput.isNotBlank() && !passwordCheck.checking
                ) {
                    Text(
                        if (editing) "确认修改" else "确认删除",
                        color = if (editing) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                    )
                }
            },
            dismissButton = {
                TextButton(onClick = {
                    pendingEdit = null
                    pendingDelete = null
                    ledgerViewModel.clearPasswordError()
                }) { Text("取消") }
            }
        )
    }
}

@Composable
private fun LedgerDetailView(
    state: LedgerUiState,
    viewModel: LedgerViewModel,
    onDayClick: (String) -> Unit,
    onDelete: (LedgerEntryDto) -> Unit,
    onEdit: (LedgerEntryDto) -> Unit
) {
    Column(Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 4.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = { viewModel.prevMonth() }) {
                Icon(Icons.Filled.ChevronLeft, contentDescription = "上月")
            }
            Text(
                text = "${state.yearMonth.year}年${state.yearMonth.monthValue}月",
                modifier = Modifier.weight(1f),
                textAlign = TextAlign.Center,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            IconButton(onClick = { viewModel.nextMonth() }) {
                Icon(Icons.Filled.ChevronRight, contentDescription = "下月")
            }
            IconButton(onClick = {
                viewModel.setViewMode(if (state.viewMode == "list") "calendar" else "list")
            }) {
                Icon(
                    if (state.viewMode == "list") Icons.Filled.CalendarMonth else Icons.Filled.ViewList,
                    contentDescription = "切换视图"
                )
            }
        }

        SummaryCard(
            expense = state.summary.expenseTotal,
            income = state.summary.incomeTotal,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
        )

        if (state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) { CircularProgressIndicator() }
        } else if (state.error != null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) { Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error) }
        } else if (state.viewMode == "calendar") {
            CalendarView(state.yearMonth, state.calendar, onDayClick = onDayClick)
        } else if (state.entries.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    "本月还没有记账，点击右下角记一笔",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(state.entries, key = { it.id }) { entry ->
                    EntryCard(
                        entry = entry,
                        onDelete = { onDelete(entry) },
                        onEdit = { onEdit(entry) }
                    )
                }
            }
        }
    }
}

@Composable
private fun StatsDetailView(
    state: StatsUiState,
    viewModel: StatsViewModel
) {
    Column(Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            FilterChip(
                selected = state.period == "month",
                onClick = { viewModel.setPeriod("month") },
                label = { Text("按月") }
            )
            Spacer(Modifier.width(8.dp))
            FilterChip(
                selected = state.period == "year",
                onClick = { viewModel.setPeriod("year") },
                label = { Text("按年") }
            )
            Spacer(Modifier.weight(1f))
            IconButton(onClick = { viewModel.prev() }) {
                Icon(Icons.Filled.ChevronLeft, contentDescription = "上一周期")
            }
            Text(
                text = if (state.period == "year") "${state.year}年" else "${state.yearMonth.year}年${state.yearMonth.monthValue}月",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            IconButton(onClick = { viewModel.next() }) {
                Icon(Icons.Filled.ChevronRight, contentDescription = "下一周期")
            }
        }

        if (state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) { CircularProgressIndicator() }
        } else if (state.error != null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) { Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error) }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    SummaryCard(
                        expense = state.summary.expenseTotal,
                        income = state.summary.incomeTotal,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                }
                item {
                    Text("支出分类", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                if (state.summary.expenseByCategory.isEmpty()) {
                    item { Text("暂无支出", color = MaterialTheme.colorScheme.onSurfaceVariant) }
                } else {
                    items(state.summary.expenseByCategory) { cat ->
                        CategoryBar(cat, state.summary.expenseTotal, ExpenseRed)
                    }
                }
                item {
                    Spacer(Modifier.height(8.dp))
                    Text("收入分类", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                if (state.summary.incomeByCategory.isEmpty()) {
                    item { Text("暂无收入", color = MaterialTheme.colorScheme.onSurfaceVariant) }
                } else {
                    items(state.summary.incomeByCategory) { cat ->
                        CategoryBar(cat, state.summary.incomeTotal, IncomeGreen)
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryCard(expense: Double, income: Double, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .shadow(8.dp, RoundedCornerShape(20.dp))
            .clip(RoundedCornerShape(20.dp))
            .background(Brush.horizontalGradient(listOf(WarmCoral, WarmPeach)))
            .padding(20.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            SummaryColumn("支出", expense)
            SummaryDivider()
            SummaryColumn("收入", income)
            SummaryDivider()
            SummaryColumn("结余", income - expense)
        }
    }
}

@Composable
private fun SummaryColumn(label: String, value: Double) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.9f))
        Spacer(Modifier.height(4.dp))
        Text(
            formatAmount(value),
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )
    }
}

@Composable
private fun SummaryDivider() {
    Box(
        modifier = Modifier
            .size(width = 1.dp, height = 40.dp)
            .background(Color.White.copy(alpha = 0.35f))
    )
}

@Composable
private fun CategoryBar(cat: CategoryStat, total: Double, color: Color) {
    val fraction = if (total <= 0) 0f else (cat.amount / total).toFloat().coerceIn(0f, 1f)
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(cat.category, style = MaterialTheme.typography.bodyLarge)
            Text(
                "${formatAmount(cat.amount)}元",
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Bold
            )
        }
        Spacer(Modifier.height(4.dp))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(10.dp)
                .clip(RoundedCornerShape(5.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(fraction)
                    .height(10.dp)
                    .clip(RoundedCornerShape(5.dp))
                    .background(color)
            )
        }
    }
}

@Composable
private fun CalendarView(
    yearMonth: YearMonth,
    calendar: List<CalendarDayDto>,
    onDayClick: (String) -> Unit
) {
    val daysInMonth = yearMonth.lengthOfMonth()
    val firstDayOfWeek = yearMonth.atDay(1).dayOfWeek.value % 7
    val totalCells = ((firstDayOfWeek + daysInMonth) + 6) / 7 * 7
    val dailyMap = calendar.associateBy { it.date }
    Column(modifier = Modifier.fillMaxWidth().padding(8.dp)) {
        Row(modifier = Modifier.fillMaxWidth()) {
            listOf("日", "一", "二", "三", "四", "五", "六").forEach {
                Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        Spacer(Modifier.height(4.dp))
        for (week in 0 until totalCells step 7) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                for (i in 0 until 7) {
                    val cell = week + i
                    val dayNum = cell - firstDayOfWeek + 1
                    if (dayNum in 1..daysInMonth) {
                        val date = yearMonth.atDay(dayNum).toString()
                        val day = dailyMap[date]
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .height(68.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))
                                .clickable { onDayClick(date) }
                                .padding(2.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text(dayNum.toString(), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
                            if (day != null) {
                                val expItems = if (day.expenseItems.isNotEmpty()) day.expenseItems
                                else if (day.expense > 0) listOf(AmountItemDto("CNY", day.expense, day.expense))
                                else emptyList()
                                val incItems = if (day.incomeItems.isNotEmpty()) day.incomeItems
                                else if (day.income > 0) listOf(AmountItemDto("CNY", day.income, day.income))
                                else emptyList()
                                expItems.forEach { item ->
                                    val unit = if (item.currency == "CNY") "元" else LedgerCurrencies.name(item.currency)
                                    Text("-${formatAmount(item.amount)}$unit", style = MaterialTheme.typography.labelSmall, color = ExpenseRed, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                }
                                incItems.forEach { item ->
                                    val unit = if (item.currency == "CNY") "元" else LedgerCurrencies.name(item.currency)
                                    Text("+${formatAmount(item.amount)}$unit", style = MaterialTheme.typography.labelSmall, color = IncomeGreen, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                }
                            }
                        }
                    } else {
                        Box(modifier = Modifier.weight(1f).height(68.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun EntryCard(entry: LedgerEntryDto, onDelete: () -> Unit, onEdit: () -> Unit) {
    val isExpense = entry.entryType != "income"
    val amountColor = if (isExpense) ExpenseRed else IncomeGreen
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .background(amountColor.copy(alpha = 0.15f), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    entry.category.take(1),
                    color = amountColor,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    entry.category,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Medium
                )
                val subtitle = buildString {
                    if (entry.note.isNotBlank()) append(entry.note).append(" · ")
                    append(entry.entryDate)
                }
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                val items = if (entry.amounts.isNotEmpty()) entry.amounts
                else listOf(AmountItemDto(entry.currency, entry.amount, entry.amountCny))
                items.forEachIndexed { i, item ->
                    val unit = if (item.currency == "CNY") "元" else LedgerCurrencies.name(item.currency)
                    Text(
                        "${if (isExpense) "-" else "+"}${formatAmount(item.amount)} $unit",
                        style = if (i == 0) MaterialTheme.typography.titleMedium else MaterialTheme.typography.bodySmall,
                        fontWeight = if (i == 0) FontWeight.Bold else FontWeight.Normal,
                        color = amountColor,
                        maxLines = 1
                    )
                }
                if (items.size > 1 || items.firstOrNull()?.currency != "CNY") {
                    Text(
                        "≈¥${formatAmount(entry.amountCny)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Row {
                IconButton(
                    onClick = onEdit,
                    modifier = Modifier.size(30.dp)
                ) {
                    Icon(
                        Icons.Filled.Edit,
                        contentDescription = "编辑",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(17.dp)
                    )
                }
                IconButton(
                    onClick = onDelete,
                    modifier = Modifier.size(30.dp)
                ) {
                    Icon(
                        Icons.Filled.Delete,
                        contentDescription = "删除",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(17.dp)
                    )
                }
            }
        }
    }
}