package com.swimanalysis.app.ui.screen

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
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
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CompareScreenFull(
    navController: NavController,
    viewModel: RecordsViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()
    val selectedIds = remember { mutableStateListOf<String>() }
    var compareResult by remember { mutableStateOf<Map<String, Any>?>(null) }
    var isLoading by remember { mutableStateOf(false) }

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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            Text(
                text = "选择 2-4 条记录进行对比",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(8.dp))

            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                items(state.records) { record ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        onClick = {
                            if (selectedIds.contains(record.id)) {
                                selectedIds.remove(record.id)
                            } else if (selectedIds.size < 4) {
                                selectedIds.add(record.id)
                            }
                        },
                        elevation = CardDefaults.cardElevation(
                            defaultElevation = if (selectedIds.contains(record.id)) 4.dp else 1.dp
                        )
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Checkbox(
                                checked = selectedIds.contains(record.id),
                                onCheckedChange = {
                                    if (it) {
                                        if (selectedIds.size < 4) selectedIds.add(record.id)
                                    } else {
                                        selectedIds.remove(record.id)
                                    }
                                }
                            )
                            Column {
                                Text(
                                    text = record.swimmerName,
                                    style = MaterialTheme.typography.titleSmall
                                )
                                Text(
                                    text = "${record.raceDistance}米${record.strokeType}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                record.raceName?.let {
                                    Text(
                                        text = it,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                selectedIds.forEach { id ->
                    AssistChip(
                        onClick = { selectedIds.remove(id) },
                        label = { Text(id.takeLast(6)) }
                    )
                }
            }

            Spacer(modifier = Modifier.height(8.dp))
            Button(
                onClick = {
                    /* 触发对比 */
                    isLoading = true
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = selectedIds.size >= 2 && !isLoading
            ) {
                Text("开始对比 (${selectedIds.size})")
            }

            compareResult?.let { result ->
                Spacer(modifier = Modifier.height(16.dp))
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("对比结果", style = MaterialTheme.typography.titleMedium)
                        result.forEach { (key, value) ->
                            Text("$key: $value", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}