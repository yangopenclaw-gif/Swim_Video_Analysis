package com.swimanalysis.app.ui.screen.agent

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.ScheduleDto
import com.swimanalysis.app.data.repository.AgentRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ScheduleUiState(
    val schedules: List<ScheduleDto> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null
)

@HiltViewModel
class ScheduleViewModel @Inject constructor(
    private val repository: AgentRepository,
    private val scheduleSync: ScheduleSyncManager
) : ViewModel() {
    private val _state = MutableStateFlow(ScheduleUiState())
    val state: StateFlow<ScheduleUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val items = repository.listSchedules()
                _state.update { it.copy(loading = false, schedules = items) }
                scheduleSync.sync()
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    fun delete(id: String) {
        viewModelScope.launch {
            try {
                repository.deleteSchedule(id)
                load()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }
}