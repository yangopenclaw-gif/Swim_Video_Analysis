package com.swimanalysis.app.ui.screen.ledger

import android.app.Activity
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavController

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun AddEntryScreen(
    navController: NavController,
    viewModel: AddEntryViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    val voiceLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val text = result.data
                ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                ?.firstOrNull()
            if (!text.isNullOrBlank()) {
                viewModel.parseVoice(text)
            }
        }
    }

    val launchVoice = {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "说出记账内容，例如：今天午饭花了30块")
        }
        voiceLauncher.launch(intent)
    }

    LaunchedEffect(state.submitSuccess) {
        if (state.submitSuccess) {
            viewModel.clearSubmitSuccess()
            navController.popBackStack()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (state.isEdit) "编辑记录" else "记一笔") },
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
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = state.entryType == "expense",
                    onClick = { viewModel.setEntryType("expense") },
                    label = { Text("支出") }
                )
                FilterChip(
                    selected = state.entryType == "income",
                    onClick = { viewModel.setEntryType("income") },
                    label = { Text("收入") }
                )
            }

            OutlinedTextField(
                value = state.amountText,
                onValueChange = viewModel::setAmount,
                label = { Text("金额") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth()
            )

            Text("币种", style = MaterialTheme.typography.labelLarge)
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                LedgerCurrencies.LIST.forEach { (code, name) ->
                    FilterChip(
                        selected = state.currency == code,
                        onClick = { viewModel.setCurrency(code) },
                        label = { Text(name) }
                    )
                }
            }

            val categories = if (state.entryType == "expense") {
                LedgerCategories.EXPENSE
            } else {
                LedgerCategories.INCOME
            }
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                categories.forEach { cat ->
                    FilterChip(
                        selected = state.category == cat,
                        onClick = { viewModel.setCategory(cat) },
                        label = { Text(cat) }
                    )
                }
            }

            OutlinedTextField(
                value = state.note,
                onValueChange = viewModel::setNote,
                label = { Text("备注") },
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = state.entryDate,
                onValueChange = viewModel::setDate,
                label = { Text("日期（YYYY-MM-DD）") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedButton(
                onClick = launchVoice,
                enabled = !state.isParsing,
                modifier = Modifier.fillMaxWidth()
            ) {
                if (state.isParsing) {
                    CircularProgressIndicator(modifier = Modifier.height(20.dp))
                } else {
                    Icon(Icons.Filled.Mic, contentDescription = null)
                }
                Spacer(Modifier.width(8.dp))
                Text(if (state.isParsing) "识别中…" else "语音录入")
            }

            state.parseError?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }
            state.error?.let {
                Text(it, color = MaterialTheme.colorScheme.error)
            }

            Button(
                onClick = viewModel::submit,
                enabled = !state.submitting,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                if (state.submitting) {
                    CircularProgressIndicator(modifier = Modifier.height(20.dp), color = MaterialTheme.colorScheme.onPrimary)
                } else {
                    Text("保存")
                }
            }
        }
    }
}