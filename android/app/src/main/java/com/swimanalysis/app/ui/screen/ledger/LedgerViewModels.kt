package com.swimanalysis.app.ui.screen.ledger

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.swimanalysis.app.data.model.LedgerEntryDto
import com.swimanalysis.app.data.model.LedgerSummary
import com.swimanalysis.app.data.model.UpdateLedgerEntryRequest
import com.swimanalysis.app.data.repository.LedgerRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import javax.inject.Inject

object LedgerCategories {
    val EXPENSE = listOf("自我消费", "请客吃饭", "娱乐", "餐饮", "交通", "购物", "居住", "医疗", "教育", "人情往来", "其他")
    val INCOME = listOf("工资", "奖金", "理财", "红包", "其他")
}

object LedgerCurrencies {
    val LIST = listOf(
        "CNY" to "人民币",
        "USD" to "美元",
        "EUR" to "欧元",
        "GBP" to "英镑",
        "EGP" to "埃镑",
        "HKD" to "港币",
        "JPY" to "日元"
    )

    fun name(code: String): String = LIST.find { it.first == code }?.second ?: code
}

data class LedgerUiState(
    val yearMonth: YearMonth = YearMonth.now(),
    val entries: List<LedgerEntryDto> = emptyList(),
    val summary: LedgerSummary = LedgerSummary(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class LedgerViewModel @Inject constructor(
    private val repository: LedgerRepository
) : ViewModel() {
    private val _state = MutableStateFlow(LedgerUiState())
    val state: StateFlow<LedgerUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        val ym = _state.value.yearMonth
        _state.update { it.copy(isLoading = true, error = null) }
        viewModelScope.launch {
            try {
                val entries = repository.getEntries(ym.year.toString(), ym.monthValue.toString())
                val summary = repository.getSummary(ym.year.toString(), ym.monthValue.toString())
                _state.update { it.copy(isLoading = false, entries = entries, summary = summary) }
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    fun prevMonth() {
        _state.update { it.copy(yearMonth = it.yearMonth.minusMonths(1)) }
        load()
    }

    fun nextMonth() {
        _state.update { it.copy(yearMonth = it.yearMonth.plusMonths(1)) }
        load()
    }

    fun deleteEntry(id: String) {
        viewModelScope.launch {
            try {
                repository.deleteEntry(id)
                load()
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun clearError() {
        _state.update { it.copy(error = null) }
    }
}

data class StatsUiState(
    val period: String = "month",
    val yearMonth: YearMonth = YearMonth.now(),
    val year: Int = YearMonth.now().year,
    val summary: LedgerSummary = LedgerSummary(),
    val isLoading: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class StatsViewModel @Inject constructor(
    private val repository: LedgerRepository
) : ViewModel() {
    private val _state = MutableStateFlow(StatsUiState())
    val state: StateFlow<StatsUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(isLoading = true, error = null) }
        val s = _state.value
        val year = if (s.period == "year") s.year.toString() else s.yearMonth.year.toString()
        val month = if (s.period == "month") s.yearMonth.monthValue.toString() else null
        viewModelScope.launch {
            try {
                val summary = repository.getSummary(year, month)
                _state.update { it.copy(isLoading = false, summary = summary) }
            } catch (e: Exception) {
                _state.update { it.copy(isLoading = false, error = e.message) }
            }
        }
    }

    fun setPeriod(period: String) {
        _state.update { it.copy(period = period) }
        load()
    }

    fun prev() {
        if (_state.value.period == "year") {
            _state.update { it.copy(year = it.year - 1) }
        } else {
            _state.update { it.copy(yearMonth = it.yearMonth.minusMonths(1)) }
        }
        load()
    }

    fun next() {
        if (_state.value.period == "year") {
            _state.update { it.copy(year = it.year + 1) }
        } else {
            _state.update { it.copy(yearMonth = it.yearMonth.plusMonths(1)) }
        }
        load()
    }
}

data class AddEntryUiState(
    val entryType: String = "expense",
    val amountText: String = "",
    val category: String = "其他",
    val note: String = "",
    val entryDate: String = LocalDate.now().toString(),
    val currency: String = "CNY",
    val isEdit: Boolean = false,
    val isParsing: Boolean = false,
    val parseError: String? = null,
    val submitting: Boolean = false,
    val submitSuccess: Boolean = false,
    val error: String? = null
)

@HiltViewModel
class AddEntryViewModel @Inject constructor(
    private val repository: LedgerRepository,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {
    private val entryId: String? = savedStateHandle["entryId"]
    private val _state = MutableStateFlow(AddEntryUiState(isEdit = entryId != null))
    val state: StateFlow<AddEntryUiState> = _state.asStateFlow()

    init {
        entryId?.let { loadEntry(it) }
    }

    fun setEntryType(type: String) {
        val category = if (type == "expense") "其他" else "其他"
        _state.update { it.copy(entryType = type, category = category) }
    }

    fun setAmount(text: String) = _state.update { it.copy(amountText = text) }
    fun setCategory(category: String) = _state.update { it.copy(category = category) }
    fun setNote(text: String) = _state.update { it.copy(note = text) }
    fun setDate(text: String) = _state.update { it.copy(entryDate = text) }
    fun setCurrency(code: String) = _state.update { it.copy(currency = code) }

    private fun loadEntry(id: String) {
        viewModelScope.launch {
            try {
                val entry = repository.getEntries(null, null).find { it.id == id }
                if (entry != null) {
                    _state.update {
                        it.copy(
                            entryType = entry.entryType,
                            amountText = formatAmount(entry.amount),
                            category = entry.category,
                            note = entry.note,
                            entryDate = entry.entryDate,
                            currency = entry.currency.ifBlank { "CNY" }
                        )
                    }
                }
            } catch (e: Exception) {
                _state.update { it.copy(error = e.message) }
            }
        }
    }

    fun parseVoice(text: String) {
        if (text.isBlank()) return
        _state.update { it.copy(isParsing = true, parseError = null) }
        viewModelScope.launch {
            try {
                val result = repository.parseVoice(text)
                val data = result.data
                val amount = data.amount
                if (amount <= 0) {
                    _state.update { it.copy(isParsing = false, parseError = "未识别出金额") }
                } else {
                    _state.update {
                        it.copy(
                            isParsing = false,
                            entryType = if (data.type == "income") "income" else "expense",
                            amountText = formatAmount(amount),
                            category = data.category.ifBlank { "其他" },
                            note = data.note,
                            entryDate = data.date.ifBlank { LocalDate.now().toString() }
                        )
                    }
                }
            } catch (e: Exception) {
                _state.update { it.copy(isParsing = false, parseError = e.message) }
            }
        }
    }

    fun submit() {
        val amount = _state.value.amountText.toDoubleOrNull()
        if (amount == null || amount <= 0) {
            _state.update { it.copy(error = "请输入有效金额") }
            return
        }
        _state.update { it.copy(submitting = true, error = null) }
        val s = _state.value
        viewModelScope.launch {
            try {
                if (entryId != null) {
                    repository.updateEntry(
                        entryId,
                        UpdateLedgerEntryRequest(
                            entryType = s.entryType,
                            amount = amount,
                            category = s.category,
                            note = s.note,
                            entryDate = s.entryDate,
                            currency = s.currency
                        )
                    )
                } else {
                    repository.createEntry(s.entryType, amount, s.category, s.note, s.entryDate, s.currency)
                }
                _state.update { it.copy(submitting = false, submitSuccess = true) }
            } catch (e: Exception) {
                _state.update { it.copy(submitting = false, error = e.message) }
            }
        }
    }

    fun clearSubmitSuccess() = _state.update { it.copy(submitSuccess = false) }
    fun clearError() = _state.update { it.copy(error = null) }

    companion object {
        fun formatAmount(value: Double): String {
            return if (value == value.toLong().toDouble()) {
                value.toLong().toString()
            } else {
                String.format("%.2f", value)
            }
        }
    }
}