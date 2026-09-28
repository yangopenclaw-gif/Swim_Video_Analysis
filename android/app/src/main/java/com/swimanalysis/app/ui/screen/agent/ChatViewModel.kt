package com.swimanalysis.app.ui.screen.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
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
    val error: String? = null
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
                    _state.update { it.copy(messages = msgs.map { m -> ChatUiMessage(m.role, m.content) }) }
                }
            } catch (_: Exception) {
            }
        }
    }

    fun newConversation() {
        streamJob?.cancel()
        conversationId = null
        _state.update { ChatUiState() }
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
}