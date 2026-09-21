package com.swimanalysis.app.data.api

import com.swimanalysis.app.data.model.CreateLedgerEntryRequest
import com.swimanalysis.app.data.model.LedgerEntryDto
import com.swimanalysis.app.data.model.LedgerSummary
import com.swimanalysis.app.data.model.ParseVoiceRequest
import com.swimanalysis.app.data.model.ParseVoiceResponse
import com.swimanalysis.app.data.model.UpdateLedgerEntryRequest
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface LedgerApi {

    @POST("/api/ledger/entries")
    suspend fun createEntry(@Body body: CreateLedgerEntryRequest): Map<String, String>

    @GET("/api/ledger/entries")
    suspend fun getEntries(
        @Query("year") year: String?,
        @Query("month") month: String?
    ): List<LedgerEntryDto>

    @PUT("/api/ledger/entries/{id}")
    suspend fun updateEntry(
        @Path("id") id: String,
        @Body body: UpdateLedgerEntryRequest
    ): Map<String, String>

    @DELETE("/api/ledger/entries/{id}")
    suspend fun deleteEntry(@Path("id") id: String): Map<String, String>

    @GET("/api/ledger/summary")
    suspend fun getSummary(
        @Query("year") year: String?,
        @Query("month") month: String?
    ): LedgerSummary

    @POST("/api/ledger/parse_voice")
    suspend fun parseVoice(@Body body: ParseVoiceRequest): ParseVoiceResponse
}