package com.swimanalysis.app.ui.screen.agent

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.ConversationDto
import com.swimanalysis.app.data.repository.AgentRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ChatUiMessage(
    val role: String,
    val content: String
)

data class ChatUiState(
    val messages: List<ChatUiMessage> = emptyList(),
    val isSending: Boolean = false,
    val streamingText: String = "",
    val statusText: String = "",
    val error: String? = null,
    val imageExtracting: Boolean = false,
    val extractedTitle: String = "",
    val extractedText: String = "",
    val imageError: String? = null,
    val docParsing: Boolean = false,
    val docFilename: String = "",
    val docText: String = "",
    val docError: String? = null,
    val conversations: List<ConversationDto> = emptyList(),
    val showHistory: Boolean = false
)

@HiltViewModel
class ChatViewModel @Inject constructor(
    private val repository: AgentRepository,
    private val scheduleSync: ScheduleSyncManager
) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var conversationId: String? = null
    private var streamJob: Job? = null
    private var imageJob: Job? = null
    private var docJob: Job? = null

    init {
        loadLatestConversation()
    }

    private fun loadLatestConversation() {
        viewModelScope.launch {
            try {
                val convs = repository.listConversations()
                if (convs.isNotEmpty()) {
                    val latest = convs.first()
                    conversationId = latest.id
                    val msgs = repository.getMessages(latest.id)
                    _state.update { it.copy(messages = msgs.map { m -> ChatUiMessage(m.role, m.content) }) }
                }
            } catch (_: Exception) {
            }
        }
    }

    fun newConversation() {
        streamJob?.cancel()
        conversationId = null
        _state.update {
            it.copy(
                messages = emptyList(),
                isSending = false,
                streamingText = "",
                statusText = "",
                error = null
            )
        }
    }

    fun toggleHistory(show: Boolean) {
        if (show) loadConversations()
        _state.update { it.copy(showHistory = show) }
    }

    fun loadConversations() {
        viewModelScope.launch {
            try {
                val convs = repository.listConversations()
                _state.update { it.copy(conversations = convs) }
            } catch (_: Exception) {
            }
        }
    }

    fun switchConversation(id: String) {
        viewModelScope.launch {
            try {
                val msgs = repository.getMessages(id)
                conversationId = id
                _state.update {
                    it.copy(
                        messages = msgs.map { m -> ChatUiMessage(m.role, m.content) },
                        streamingText = "", statusText = "", error = null,
                        showHistory = false
                    )
                }
            } catch (_: Exception) {
            }
        }
    }

    fun deleteConversation(id: String) {
        viewModelScope.launch {
            try {
                repository.deleteConversation(id)
                if (conversationId == id) {
                    conversationId = null
                    _state.update { it.copy(messages = emptyList(), streamingText = "") }
                }
                loadConversations()
            } catch (_: Exception) {
            }
        }
    }

    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || _state.value.isSending) return
        _state.update {
            it.copy(
                messages = it.messages + ChatUiMessage("user", trimmed),
                isSending = true, streamingText = "", statusText = "", error = null
            )
        }
        streamJob = viewModelScope.launch {
            val assistant = StringBuilder()
            try {
                repository.streamChat(trimmed, conversationId).collect { event ->
                    when (event.type) {
                        "meta" -> event.conversationId?.let { conversationId = it }
                        "status" -> _state.update { it.copy(statusText = event.text) }
                        "token" -> {
                            assistant.append(event.text)
                            _state.update { it.copy(streamingText = assistant.toString()) }
                        }
                        "error" -> _state.update { it.copy(error = event.text) }
                    }
                }
                val final = assistant.toString()
                _state.update {
                    if (final.isNotBlank()) {
                        it.copy(
                            messages = it.messages + ChatUiMessage("assistant", final),
                            isSending = false, streamingText = "", statusText = ""
                        )
                    } else {
                        it.copy(isSending = false, streamingText = "", statusText = "")
                    }
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(isSending = false, streamingText = "", statusText = "", error = e.message)
                }
            }
            scheduleSync.sync()
        }
    }

    fun stopStreaming() {
        streamJob?.cancel()
        val text = _state.value.streamingText
        _state.update {
            if (text.isNotBlank()) {
                it.copy(
                    messages = it.messages + ChatUiMessage("assistant", text),
                    isSending = false, streamingText = "", statusText = ""
                )
            } else {
                it.copy(isSending = false, streamingText = "", statusText = "")
            }
        }
    }

    fun clearError() = _state.update { it.copy(error = null) }

    fun extractImage(uri: Uri) {
        if (_state.value.imageExtracting) return
        _state.update { it.copy(imageExtracting = true, imageError = null) }
        imageJob = viewModelScope.launch {
            try {
                val text = repository.extractImage(uri)
                _state.update { it.copy(imageExtracting = false, extractedText = text, extractedTitle = "") }
            } catch (e: Exception) {
                _state.update { it.copy(imageExtracting = false, imageError = e.message) }
            }
        }
    }

    fun setExtractedTitle(text: String) = _state.update { it.copy(extractedTitle = text) }
    fun setExtractedText(text: String) = _state.update { it.copy(extractedText = text) }

    fun saveExtractedToKb() {
        val title = _state.value.extractedTitle.trim()
        val content = _state.value.extractedText.trim()
        if (content.isEmpty()) {
            _state.update { it.copy(imageError = "抽取内容为空") }
            return
        }
        viewModelScope.launch {
            try {
                repository.uploadDocument(title.ifBlank { "图片信息" }, content)
                _state.update { it.copy(extractedTitle = "", extractedText = "", imageError = null) }
            } catch (e: Exception) {
                _state.update { it.copy(imageError = e.message) }
            }
        }
    }

    fun dismissImageResult() {
        imageJob?.cancel()
        _state.update {
            it.copy(imageExtracting = false, extractedTitle = "", extractedText = "", imageError = null)
        }
    }

    fun parseDocument(uri: Uri) {
        if (_state.value.docParsing) return
        _state.update { it.copy(docParsing = true, docError = null) }
        docJob = viewModelScope.launch {
            try {
                val result = repository.parseDocument(uri)
                _state.update {
                    it.copy(docParsing = false, docFilename = result.filename, docText = result.text)
                }
            } catch (e: Exception) {
                _state.update { it.copy(docParsing = false, docError = e.message) }
            }
        }
    }

    fun setDocText(text: String) = _state.update { it.copy(docText = text) }

    fun saveDocToKb() {
        val content = _state.value.docText.trim()
        if (content.isEmpty()) {
            _state.update { it.copy(docError = "解析内容为空") }
            return
        }
        viewModelScope.launch {
            try {
                val title = _state.value.docFilename.ifBlank { "文档" }
                repository.uploadDocument(title, content)
                _state.update { it.copy(docFilename = "", docText = "", docError = null) }
            } catch (e: Exception) {
                _state.update { it.copy(docError = e.message) }
            }
        }
    }

    fun dismissDocResult() {
        docJob?.cancel()
        _state.update { it.copy(docParsing = false, docFilename = "", docText = "", docError = null) }
    }
}