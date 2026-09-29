package com.swimanalysis.app.data.api

import com.swimanalysis.app.data.model.ConversationListResponse
import com.swimanalysis.app.data.model.DocParseResponse
import com.swimanalysis.app.data.model.DocumentListResponse
import com.swimanalysis.app.data.model.ImageExtractResponse
import com.swimanalysis.app.data.model.KbUploadRequest
import com.swimanalysis.app.data.model.KbUploadResponse
import com.swimanalysis.app.data.model.MessageListResponse
import com.swimanalysis.app.data.model.NoteCreateRequest
import com.swimanalysis.app.data.model.NoteListResponse
import com.swimanalysis.app.data.model.ScheduleCreateRequest
import com.swimanalysis.app.data.model.ScheduleListResponse
import com.swimanalysis.app.data.model.UploadFileResponse
import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path

interface AgentApi {

    @GET("/api/agent/conversations")
    suspend fun listConversations(): ConversationListResponse

    @GET("/api/agent/conversations/{id}/messages")
    suspend fun getMessages(@Path("id") id: String): MessageListResponse

    @DELETE("/api/agent/conversations/{id}")
    suspend fun deleteConversation(@Path("id") id: String): Map<String, String>

    @GET("/api/agent/schedules")
    suspend fun listSchedules(): ScheduleListResponse

    @POST("/api/agent/schedules")
    suspend fun createSchedule(@Body body: ScheduleCreateRequest): Map<String, String>

    @DELETE("/api/agent/schedules/{id}")
    suspend fun deleteSchedule(@Path("id") id: String): Map<String, String>

    @POST("/api/agent/kb/upload")
    suspend fun uploadDocument(@Body body: KbUploadRequest): KbUploadResponse

    @Multipart
    @POST("/api/agent/kb/extract_image")
    suspend fun extractImage(@Part file: MultipartBody.Part): ImageExtractResponse

    @Multipart
    @POST("/api/agent/doc/parse")
    suspend fun parseDocument(@Part file: MultipartBody.Part): DocParseResponse

    @Multipart
    @POST("/api/agent/upload_file")
    suspend fun uploadFile(@Part file: MultipartBody.Part): UploadFileResponse

    @GET("/api/agent/kb/documents")
    suspend fun listDocuments(): DocumentListResponse

    @DELETE("/api/agent/kb/documents/{id}")
    suspend fun deleteDocument(@Path("id") id: String): Map<String, String>

    @GET("/api/agent/notes")
    suspend fun listNotes(): NoteListResponse

    @POST("/api/agent/notes")
    suspend fun createNote(@Body body: NoteCreateRequest): Map<String, String>

    @PUT("/api/agent/notes/{id}")
    suspend fun updateNote(@Path("id") id: String, @Body body: NoteCreateRequest): Map<String, String>

    @DELETE("/api/agent/notes/{id}")
    suspend fun deleteNote(@Path("id") id: String): Map<String, String>
}