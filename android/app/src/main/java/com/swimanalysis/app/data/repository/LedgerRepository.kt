package com.swimanalysis.app.data.repository

import com.swimanalysis.app.data.api.LedgerApi
import com.swimanalysis.app.data.model.AuthRequest
import com.swimanalysis.app.data.model.AuthResponse
import com.swimanalysis.app.data.model.CreateLedgerEntryRequest
import com.swimanalysis.app.data.model.CurrencyListResponse
import com.swimanalysis.app.data.model.LedgerEntryDto
import com.swimanalysis.app.data.model.LedgerSummary
import com.swimanalysis.app.data.model.ParseVoiceRequest
import com.swimanalysis.app.data.model.ParseVoiceResponse
import com.swimanalysis.app.data.model.UpdateLedgerEntryRequest
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class LedgerRepository @Inject constructor(
    private val api: LedgerApi
) {
    suspend fun createEntry(entryType: String, amount: Double, category: String, note: String, entryDate: String, currency: String) =
        api.createEntry(CreateLedgerEntryRequest(entryType, amount, category, note, entryDate, currency))

    suspend fun register(username: String, password: String): AuthResponse =
        api.register(AuthRequest(username, password))

    suspend fun login(username: String, password: String): AuthResponse =
        api.login(AuthRequest(username, password))

    suspend fun getCurrencies(): CurrencyListResponse =
        api.getCurrencies()

    suspend fun getEntries(year: String?, month: String?): List<LedgerEntryDto> =
        api.getEntries(year, month)

    suspend fun updateEntry(id: String, body: UpdateLedgerEntryRequest) =
        api.updateEntry(id, body)

    suspend fun deleteEntry(id: String) =
        api.deleteEntry(id)

    suspend fun getSummary(year: String?, month: String?): LedgerSummary =
        api.getSummary(year, month)

    suspend fun parseVoice(text: String): ParseVoiceResponse =
        api.parseVoice(ParseVoiceRequest(text))
}