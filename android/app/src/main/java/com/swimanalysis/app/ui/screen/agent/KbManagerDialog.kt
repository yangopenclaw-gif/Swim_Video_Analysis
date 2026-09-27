package com.swimanalysis.app.ui.screen.agent

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.DocumentDto
import com.swimanalysis.app.data.repository.AgentRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class KbUiState(
    val documents: List<DocumentDto> = emptyList(),
    val title: String = "",
    val content: String = "",
    val loading: Boolean = false,
    val uploading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class KbViewModel @Inject constructor(
    private val repository: AgentRepository
) : ViewModel() {
    private val _state = MutableStateFlow(KbUiState())
    val state: StateFlow<KbUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val docs = repository.listDocuments()
                _state.update { it.copy(loading = false, documents = docs) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun setTitle(text: String) = _state.update { it.copy(title = text) }
    fun setContent(text: String) = _state.update { it.copy(content = text) }

    fun upload() {
        val title = _state.value.title.trim()
        val content = _state.value.content.trim()
        if (content.isEmpty()) {
            _state.update { it.copy(error = "请先粘贴文档内容") }
            return
        }
        _state.update { it.copy(uploading = true, error = null) }
        viewModelScope.launch {
            try {
                repository.uploadDocument(title.ifBlank { "未命名文档" }, content)
                _state.update { it.copy(uploading = false, title = "", content = "") }
                load()
            } catch (e: Exception) {
                _state.update { it.copy(uploading = false, error = e.message) }
            }
        }
    }

    fun delete(id: String) {
        viewModelScope.launch {
            try {
                repository.deleteDocument(id)
                load()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun clearError() = _state.update { it.copy(error = null) }
}

@Composable
fun KbManagerDialog(
    onDismiss: () -> Unit,
    viewModel: KbViewModel = hiltViewModel()
) {
    val state by viewModel.state.collectAsState()

    Dialog(onDismissRequest = onDismiss) {
        Surface(
            shape = RoundedCornerShape(20.dp),
            color = MaterialTheme.colorScheme.surface,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 520.dp)
        ) {
            Column(
                modifier = Modifier.padding(20.dp)
            ) {
                Text("个人知识库", style = MaterialTheme.typography.titleLarge)
                Text(
                    "把笔记、资料粘贴进来，助手就能基于它们回答。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(12.dp))

                OutlinedTextField(
                    value = state.title,
                    onValueChange = viewModel::setTitle,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("标题（可选）") },
                    singleLine = true
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = state.content,
                    onValueChange = viewModel::setContent,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("粘贴文档内容") },
                    minLines = 3,
                    maxLines = 5
                )
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    TextButton(
                        onClick = viewModel::upload,
                        enabled = !state.uploading
                    ) { Text(if (state.uploading) "入库中…" else "添加到知识库") }
                }

                state.error?.let {
                    Spacer(Modifier.height(4.dp))
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }

                Spacer(Modifier.height(12.dp))
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(state.documents, key = { it.id }) { doc ->
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
                                    .padding(horizontal = 12.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(doc.title, style = MaterialTheme.typography.bodyMedium)
                                    Text(
                                        "${doc.chunkCount} 个片段",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                IconButton(
                                    onClick = { viewModel.delete(doc.id) },
                                    modifier = Modifier.size(32.dp)
                                ) {
                                    Icon(
                                        Icons.Filled.Delete,
                                        contentDescription = "删除",
                                        tint = MaterialTheme.colorScheme.error,
                                        modifier = Modifier.size(18.dp)
                                    )
                                }
                            }
                        }
                    }
                }

                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
            }
        }
    }
}