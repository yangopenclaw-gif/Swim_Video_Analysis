package com.swimanalysis.app.data.api

import com.swimanalysis.app.data.model.ConversationListResponse
import com.swimanalysis.app.data.model.DocumentListResponse
import com.swimanalysis.app.data.model.KbUploadRequest
import com.swimanalysis.app.data.model.KbUploadResponse
import com.swimanalysis.app.data.model.MessageListResponse
import com.swimanalysis.app.data.model.ScheduleCreateRequest
import com.swimanalysis.app.data.model.ScheduleListResponse
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface AgentApi {

    @GET("/api/agent/conversations")
    suspend fun listConversations(): ConversationListResponse

    @GET("/api/agent/conversations/{id}/messages")
    suspend fun getMessages(@Path("id") id: String): MessageListResponse

    @GET("/api/agent/schedules")
    suspend fun listSchedules(): ScheduleListResponse

    @POST("/api/agent/schedules")
    suspend fun createSchedule(@Body body: ScheduleCreateRequest): Map<String, String>

    @DELETE("/api/agent/schedules/{id}")
    suspend fun deleteSchedule(@Path("id") id: String): Map<String, String>

    @POST("/api/agent/kb/upload")
    suspend fun uploadDocument(@Body body: KbUploadRequest): KbUploadResponse

    @GET("/api/agent/kb/documents")
    suspend fun listDocuments(): DocumentListResponse

    @DELETE("/api/agent/kb/documents/{id}")
    suspend fun deleteDocument(@Path("id") id: String): Map<String, String>
}