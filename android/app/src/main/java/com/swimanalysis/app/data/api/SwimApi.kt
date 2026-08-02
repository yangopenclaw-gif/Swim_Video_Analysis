package com.swimanalysis.app.data.api

import com.swimanalysis.app.data.model.AnalyzeExistingRequest
import com.swimanalysis.app.data.model.AnalyzeProgressResponse
import com.swimanalysis.app.data.model.AnalyzeRequest
import com.swimanalysis.app.data.model.ArchiveRequest
import com.swimanalysis.app.data.model.CalculateRequest
import com.swimanalysis.app.data.model.CancelUploadRequest
import com.swimanalysis.app.data.model.ChunkUploadRequest
import com.swimanalysis.app.data.model.ChunkUploadResponse
import com.swimanalysis.app.data.model.CompareEvaluateRequest
import com.swimanalysis.app.data.model.CompareTimelineRequest
import com.swimanalysis.app.data.model.CompetitionCreateRequest
import com.swimanalysis.app.data.model.CompetitionDto
import com.swimanalysis.app.data.model.CompetitionUpdateRequest
import com.swimanalysis.app.data.model.CompleteUploadRequest
import com.swimanalysis.app.data.model.CompleteUploadResponse
import com.swimanalysis.app.data.model.DeleteRequest
import com.swimanalysis.app.data.model.DuplicateCheckRequest
import com.swimanalysis.app.data.model.LinkRecordRequest
import com.swimanalysis.app.data.model.ManualRecordRequest
import com.swimanalysis.app.data.model.MarkerCreateRequest
import com.swimanalysis.app.data.model.MarkerDto
import com.swimanalysis.app.data.model.RecordDto
import com.swimanalysis.app.data.model.RecordUpdateRequest
import com.swimanalysis.app.data.model.SaveMarkerResultRequest
import com.swimanalysis.app.data.model.SwimmerProfileDto
import com.swimanalysis.app.data.model.SwimmerProfileUpdate
import com.swimanalysis.app.data.model.UploadInitRequest
import com.swimanalysis.app.data.model.UploadInitResponse
import com.swimanalysis.app.data.model.UploadStatusResponse
import com.swimanalysis.app.data.model.VideoDto
import com.swimanalysis.app.data.model.VideoFsDto
import com.swimanalysis.app.data.model.VideoUpdateRequest
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

interface SwimApi {

    @GET("/api/health")
    suspend fun health(): Map<String, String>

    @POST("/api/upload/init")
    suspend fun initUpload(@Body body: UploadInitRequest): UploadInitResponse

    @GET("/api/upload/status/{uploadId}")
    suspend fun uploadStatus(@Path("uploadId") uploadId: String): UploadStatusResponse

    @POST("/api/upload/probe")
    suspend fun uploadProbe(@Body body: RequestBody): Map<String, Int>

    @POST("/api/upload/chunk")
    suspend fun uploadChunk(@Body body: ChunkUploadRequest): ChunkUploadResponse

    @Multipart
    @POST("/api/upload/chunk")
    suspend fun uploadChunkMultipart(
        @Part("upload_id") uploadId: RequestBody,
        @Part("chunk_index") chunkIndex: RequestBody,
        @Part chunk: MultipartBody.Part
    ): ChunkUploadResponse

    @POST("/api/upload/complete")
    suspend fun completeUpload(@Body body: CompleteUploadRequest): CompleteUploadResponse

    @POST("/api/upload/cancel")
    suspend fun cancelUpload(@Body body: CancelUploadRequest): Map<String, String>

    @POST("/api/analyze/{taskId}")
    suspend fun startAnalyze(
        @Path("taskId") taskId: String,
        @Body body: AnalyzeRequest
    ): Map<String, String>

    @POST("/api/analyze_existing/{taskId}")
    suspend fun analyzeExisting(
        @Path("taskId") taskId: String,
        @Body body: AnalyzeExistingRequest
    ): Map<String, String>

    @GET("/api/analyze/progress/{taskId}")
    suspend fun analyzeProgress(@Path("taskId") taskId: String): AnalyzeProgressResponse

    @GET("/api/result/{taskId}")
    suspend fun analyzeResult(@Path("taskId") taskId: String): Map<String, Any>

    @POST("/api/archive/{taskId}")
    suspend fun archiveRecord(
        @Path("taskId") taskId: String,
        @Body body: ArchiveRequest
    ): Map<String, Any>

    @GET("/api/records/{swimmerName}")
    suspend fun getRecords(@Path("swimmerName") swimmerName: String): List<RecordDto>

    @GET("/api/all_records")
    suspend fun getAllRecords(): List<RecordDto>

    @GET("/api/compare")
    suspend fun compareRecords(
        @Query("id1") id1: String,
        @Query("id2") id2: String
    ): Map<String, Any>

    @POST("/api/compare_timeline")
    suspend fun compareTimeline(@Body body: CompareTimelineRequest): Map<String, Any>

    @GET("/api/swimmer_profile/{name}")
    suspend fun getSwimmerProfile(@Path("name") name: String): SwimmerProfileDto

    @PUT("/api/swimmer_profile/{name}")
    suspend fun updateSwimmerProfile(
        @Path("name") name: String,
        @Body body: SwimmerProfileUpdate
    ): Map<String, String>

    @Multipart
    @POST("/api/upload_avatar/{name}")
    suspend fun uploadAvatar(
        @Path("name") name: String,
        @Part avatar: MultipartBody.Part
    ): Map<String, String>

    @GET("/avatars/{filename}")
    @Streaming
    suspend fun getAvatar(@Path("filename") filename: String): ResponseBody

    @GET("/api/competitions")
    suspend fun getCompetitions(): List<CompetitionDto>

    @POST("/api/competitions")
    suspend fun createCompetition(@Body body: CompetitionCreateRequest): CompetitionDto

    @DELETE("/api/competitions/{compId}")
    suspend fun deleteCompetition(@Path("compId") compId: String): Map<String, String>

    @PUT("/api/competitions/{compId}")
    suspend fun updateCompetition(
        @Path("compId") compId: String,
        @Body body: CompetitionUpdateRequest
    ): Map<String, Any>

    @POST("/api/check_duplicate_record")
    suspend fun checkDuplicate(@Body body: DuplicateCheckRequest): Map<String, Any>

    @POST("/api/manual_record")
    suspend fun manualRecord(@Body body: ManualRecordRequest): Map<String, Any>

    @PUT("/api/records/{recordId}")
    suspend fun updateRecord(
        @Path("recordId") recordId: String,
        @Body body: RecordUpdateRequest
    ): Map<String, Any>

    @DELETE("/api/records/{taskId}")
    suspend fun deleteRecord(
        @Path("taskId") taskId: String,
        @Body body: DeleteRequest
    ): Map<String, Any>

    @GET("/api/videos")
    suspend fun getVideosFromFs(): List<VideoFsDto>

    @GET("/api/videos/list")
    suspend fun getVideosFromDb(): List<VideoDto>

    @DELETE("/api/videos/{taskId}")
    suspend fun deleteVideoFs(@Path("taskId") taskId: String): Map<String, String>

    @DELETE("/api/videos/{videoId}/delete")
    suspend fun deleteVideoDb(
        @Path("videoId") videoId: String,
        @Body body: DeleteRequest
    ): Map<String, Any>

    @GET("/api/videos/{videoId}/stream")
    @Streaming
    suspend fun streamVideo(@Path("videoId") videoId: String): ResponseBody

    @Multipart
    @POST("/api/videos/upload")
    suspend fun uploadVideoSimple(
        @Part("display_name") displayName: RequestBody,
        @Part("athlete_name") athleteName: RequestBody,
        @Part video: MultipartBody.Part
    ): Map<String, Any>

    @PUT("/api/videos/{videoId}")
    suspend fun updateVideo(
        @Path("videoId") videoId: String,
        @Body body: VideoUpdateRequest
    ): Map<String, Any>

    @GET("/api/videos/{videoId}/linked_record")
    suspend fun getLinkedRecord(@Path("videoId") videoId: String): Map<String, Any>

    @GET("/api/videos/{videoId}/markers")
    suspend fun getMarkers(@Path("videoId") videoId: String): List<MarkerDto>

    @POST("/api/videos/{videoId}/markers")
    suspend fun addMarker(
        @Path("videoId") videoId: String,
        @Body body: MarkerCreateRequest
    ): MarkerDto

    @DELETE("/api/videos/{videoId}/markers/{markerId}")
    suspend fun deleteMarker(
        @Path("videoId") videoId: String,
        @Path("markerId") markerId: String
    ): Map<String, String>

    @POST("/api/videos/{videoId}/detect_start_signal")
    suspend fun detectStartSignal(@Path("videoId") videoId: String): Map<String, Any>

    @POST("/api/videos/{videoId}/calculate_from_markers")
    suspend fun calculateFromMarkers(
        @Path("videoId") videoId: String,
        @Body body: CalculateRequest
    ): Map<String, Any>

    @POST("/api/videos/{videoId}/save_marker_result")
    suspend fun saveMarkerResult(
        @Path("videoId") videoId: String,
        @Body body: SaveMarkerResultRequest
    ): Map<String, Any>

    @POST("/api/videos/{videoId}/link_to_record")
    suspend fun linkToRecord(
        @Path("videoId") videoId: String,
        @Body body: LinkRecordRequest
    ): Map<String, Any>

    @Multipart
    @POST("/api/recognize_image")
    suspend fun recognizeImage(@Part image: MultipartBody.Part): Map<String, Any>

    @Multipart
    @POST("/api/recognize_competition")
    suspend fun recognizeCompetition(@Part image: MultipartBody.Part): Map<String, Any>

    @POST("/api/compare_evaluate")
    suspend fun compareEvaluate(@Body body: CompareEvaluateRequest): Map<String, Any>
}