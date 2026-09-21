package com.swimanalysis.app.ui.screen.ledger

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChevronLeft
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.swimanalysis.app.data.model.CategoryStat
import com.swimanalysis.app.ui.theme.ExpenseRed
import com.swimanalysis.app.ui.theme.IncomeGreen
import com.swimanalysis.app.ui.theme.WarmCoral
import com.swimanalysis.app.ui.theme.WarmPeach

private fun formatAmount(value: Double): String {
    return if (value == value.toLong().toDouble()) {
        value.toLong().toString()
    } else {
        String.format("%.2f", value)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatsScreen(
    viewModel: StatsViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("统计") },
                navigationIcon = {
                    IconButton(onClick = { viewModel.prev() }) {
                        Icon(Icons.Filled.ChevronLeft, contentDescription = "上一周期")
                    }
                },
                actions = {
                    Text(
                        text = if (state.period == "year") "${state.year}年" else "${state.yearMonth.year}年${state.yearMonth.monthValue}月",
                        modifier = Modifier.padding(end = 8.dp),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    IconButton(onClick = { viewModel.next() }) {
                        Icon(Icons.Filled.ChevronRight, contentDescription = "下一周期")
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
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FilterChip(
                    selected = state.period == "month",
                    onClick = { viewModel.setPeriod("month") },
                    label = { Text("按月") }
                )
                FilterChip(
                    selected = state.period == "year",
                    onClick = { viewModel.setPeriod("year") },
                    label = { Text("按年") }
                )
            }

            if (state.isLoading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else if (state.error != null) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    item {
                        TotalsCard(
                            expense = state.summary.expenseTotal,
                            income = state.summary.incomeTotal
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
}

@Composable
private fun TotalsCard(expense: Double, income: Double) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(8.dp, RoundedCornerShape(20.dp))
            .clip(RoundedCornerShape(20.dp))
            .background(Brush.horizontalGradient(listOf(WarmCoral, WarmPeach)))
            .padding(20.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("支出", style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.9f))
                Text(
                    formatAmount(expense),
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("收入", style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.9f))
                Text(
                    formatAmount(income),
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("结余", style = MaterialTheme.typography.bodyMedium, color = Color.White.copy(alpha = 0.9f))
                Text(
                    formatAmount(income - expense),
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
            }
        }
    }
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