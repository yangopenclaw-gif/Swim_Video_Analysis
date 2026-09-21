package com.swimanalysis.app.ui.screen

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.local.AuthStore
import com.swimanalysis.app.data.repository.LedgerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AuthUiState(
    val username: String = "",
    val password: String = "",
    val isRegister: Boolean = false,
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val repository: LedgerRepository,
    private val authStore: AuthStore
) : ViewModel() {
    private val _state = MutableStateFlow(AuthUiState())
    val state: StateFlow<AuthUiState> = _state.asStateFlow()

    val username: StateFlow<String?> = authStore.username

    fun setUsername(text: String) = _state.update { it.copy(username = text) }
    fun setPassword(text: String) = _state.update { it.copy(password = text) }
    fun setRegisterMode(register: Boolean) = _state.update { it.copy(isRegister = register, error = null) }

    fun submit() {
        val s = _state.value
        if (s.username.isBlank()) {
            _state.update { it.copy(error = "请输入用户名") }
            return
        }
        if (s.password.length < 4) {
            _state.update { it.copy(error = "密码至少4位") }
            return
        }
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            try {
                val resp = if (s.isRegister) {
                    repository.register(s.username.trim(), s.password)
                } else {
                    repository.login(s.username.trim(), s.password)
                }
                authStore.save(resp.token, resp.username.ifBlank { s.username.trim() })
                _state.update { it.copy(isLoading = false) }
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    fun logout() {
        viewModelScope.launch { authStore.clear() }
    }

    fun clearError() = _state.update { it.copy(error = null) }
}