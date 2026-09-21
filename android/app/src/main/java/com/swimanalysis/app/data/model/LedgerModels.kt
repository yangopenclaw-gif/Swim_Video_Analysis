package com.swimanalysis.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AmountItemDto(
    val currency: String = "CNY",
    val amount: Double = 0.0,
    @SerialName("amount_cny") val amountCny: Double = 0.0
)

@Serializable
data class LedgerEntryDto(
    val id: String = "",
    @SerialName("entry_type") val entryType: String = "expense",
    val amount: Double = 0.0,
    val category: String = "其他",
    val note: String = "",
    @SerialName("entry_date") val entryDate: String = "",
    val currency: String = "CNY",
    @SerialName("amount_cny") val amountCny: Double = 0.0,
    val amounts: List<AmountItemDto> = emptyList(),
    @SerialName("created_at") val createdAt: String? = null
)

@Serializable
data class CategoryStat(
    val category: String = "",
    val amount: Double = 0.0
)

@Serializable
data class LedgerSummary(
    @SerialName("expense_total") val expenseTotal: Double = 0.0,
    @SerialName("income_total") val incomeTotal: Double = 0.0,
    @SerialName("expense_by_category") val expenseByCategory: List<CategoryStat> = emptyList(),
    @SerialName("income_by_category") val incomeByCategory: List<CategoryStat> = emptyList()
)

@Serializable
data class CreateLedgerEntryRequest(
    @SerialName("entry_type") val entryType: String,
    val amount: Double,
    val category: String,
    val note: String = "",
    @SerialName("entry_date") val entryDate: String,
    val currency: String = "CNY",
    val amounts: List<AmountItemDto>? = null
)

@Serializable
data class UpdateLedgerEntryRequest(
    @SerialName("entry_type") val entryType: String? = null,
    val amount: Double? = null,
    val category: String? = null,
    val note: String? = null,
    @SerialName("entry_date") val entryDate: String? = null,
    val currency: String? = null,
    val amounts: List<AmountItemDto>? = null
)

@Serializable
data class AuthRequest(
    val username: String,
    val password: String
)

@Serializable
data class AuthResponse(
    val status: String = "",
    val token: String = "",
    val username: String = ""
)

@Serializable
data class CurrencyDto(
    val code: String = "",
    val name: String = "",
    val rate: Double = 0.0
)

@Serializable
data class CurrencyListResponse(
    val currencies: List<CurrencyDto> = emptyList()
)

@Serializable
data class ParseVoiceRequest(
    val text: String
)

@Serializable
data class VoiceParseData(
    val type: String = "expense",
    val amount: Double = 0.0,
    val currency: String = "CNY",
    val category: String = "其他",
    val note: String = "",
    val date: String = "",
    val amounts: List<AmountItemDto> = emptyList()
)
@Serializable
data class ParseVoiceResponse(
    val status: String = "",
    val data: VoiceParseData = VoiceParseData()
)