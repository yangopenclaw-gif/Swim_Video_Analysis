package com.swimanalysis.app.ui.screen

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.AnalysisResult
import com.swimanalysis.app.data.repository.SwimRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AnalyzeUiState(
    val isLoading: Boolean = true,
    val status: String = "pending",
    val progress: Int = 0,
    val message: String = "等待分析...",
    val result: AnalysisResult? = null,
    val error: String? = null,
    val isCompleted: Boolean = false
)

@HiltViewModel
class AnalyzeProgressViewModel @Inject constructor(
    private val repository: SwimRepository
) : ViewModel() {
    private val _state = MutableStateFlow(AnalyzeUiState())
    val state: StateFlow<AnalyzeUiState> = _state.asStateFlow()

    fun startPolling(taskId: String) {
        viewModelScope.launch {
            while (true) {
                try {
                    val resp = repository.analyzeProgress(taskId)
                    _state.update {
                        AnalyzeUiState(
                            isLoading = false,
                            status = resp.status,
                            progress = resp.progress,
                            message = resp.message.ifEmpty { resp.status },
                            isCompleted = resp.status == "completed" || resp.status == "failed",
                            error = if (resp.status == "failed") resp.message else null
                        )
                    }

                    if (resp.status == "completed") {
                        try {
                            val result = repository.parseAnalysisResult(taskId)
                            _state.update { it.copy(result = result) }
                        } catch (_: Exception) {}
                        break
                    }
                    if (resp.status == "failed") break

                    delay(1500)
                } catch (e: Exception) {
                    _state.update {
                        it.copy(isLoading = false, error = e.message, isCompleted = true)
                    }
                    break
                }
            }
        }
    }
}