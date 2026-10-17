package com.swimanalysis.app.ui.screen.agent


import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.ChatAttachment
import com.swimanalysis.app.data.model.ConversationDto
import com.swimanalysis.app.data.model.DatabaseDetailResponse
import com.swimanalysis.app.data.model.DatabaseOverviewDto
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
    val content: String,
    val attachments: List<ChatAttachment> = emptyList()
)

data class ChatUiState(
    val messages: List<ChatUiMessage> = emptyList(),
    val isSending: Boolean = false,
    val streamingText: String = "",
    val statusText: String = "",
    val error: String? = null,
    val scrollToBottomTick: Int = 0,

    val conversations: List<ConversationDto> = emptyList(),
    val showHistory: Boolean = false,
    val databases: List<DatabaseOverviewDto> = emptyList(),

    val databaseLoading: Boolean = false,
    val currentDatabase: DatabaseDetailResponse? = null
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
                    _state.update {
                        it.copy(
                            messages = msgs.map { m -> ChatUiMessage(m.role, m.content) },
                            scrollToBottomTick = it.scrollToBottomTick + 1
                        )
                    }
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
                        showHistory = false,
                        scrollToBottomTick = it.scrollToBottomTick + 1
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
                val attachments = mutableListOf<ChatAttachment>()
                repository.streamChat(trimmed, conversationId).collect { event ->
                    when (event.type) {
                        "meta" -> event.conversationId?.let { conversationId = it }
                        "status" -> _state.update { it.copy(statusText = event.text) }
                        "token" -> {
                            assistant.append(event.text)
                            _state.update { it.copy(streamingText = assistant.toString()) }
                        }
                        "attachment" -> attachments.add(
                            ChatAttachment(event.kind, event.filename, event.title, event.url)
                        )
                        "error" -> _state.update { it.copy(error = event.text) }
                    }
                }
                val final = assistant.toString()
                _state.update {
                    if (final.isNotBlank()) {
                        it.copy(
                            messages = it.messages + ChatUiMessage("assistant", final, attachments.toList()),
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


    fun downloadAttachment(att: ChatAttachment) {
        repository.downloadAttachment(att.url, att.filename)
    }


    fun loadDatabases() {
        if (_state.value.databaseLoading) return
        _state.update { it.copy(databaseLoading = true) }
        viewModelScope.launch {
            try {
                val dbs = repository.listDatabases()
                _state.update { it.copy(databases = dbs, databaseLoading = false) }
            } catch (e: Exception) {
                _state.update { it.copy(databaseLoading = false, error = e.message) }
            }
        }
    }

    fun openDatabase(key: String) {
        if (_state.value.databaseLoading) return
        _state.update { it.copy(databaseLoading = true) }
        viewModelScope.launch {
            try {
                val detail = repository.getDatabase(key)
                _state.update { it.copy(currentDatabase = detail, databaseLoading = false) }
            } catch (e: Exception) {
                _state.update { it.copy(databaseLoading = false, error = e.message) }
            }
        }
    }

    fun closeDatabase() {
        _state.update { it.copy(currentDatabase = null) }
    }
}