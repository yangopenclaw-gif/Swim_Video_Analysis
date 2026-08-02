package com.swimanalysis.app.data.repository

import com.swimanalysis.app.data.api.SwimApi
import com.swimanalysis.app.data.model.AnalysisResult
import com.swimanalysis.app.data.model.AnalyzeProgressResponse
import com.swimanalysis.app.data.model.ChunkUploadResponse
import com.swimanalysis.app.data.model.CompleteUploadResponse
import com.swimanalysis.app.data.model.CompetitionDto
import com.swimanalysis.app.data.model.MarkerDto
import com.swimanalysis.app.data.model.RecordDto
import com.swimanalysis.app.data.model.UploadInitResponse
import com.swimanalysis.app.data.model.UploadStatusResponse
import com.swimanalysis.app.data.model.VideoDto
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class SwimRepository @Inject constructor(
    private val api: SwimApi
) {
    suspend fun health() = api.health()

    suspend fun initUpload(
        filename: String,
        fileSize: Long,
        athleteName: String,
        displayName: String,
        competitionName: String
    ): UploadInitResponse = api.initUpload(
        com.swimanalysis.app.data.model.UploadInitRequest(
            filename = filename,
            fileSize = fileSize,
            athleteName = athleteName,
            displayName = displayName,
            competitionName = competitionName
        )
    )

    suspend fun uploadStatus(uploadId: String): UploadStatusResponse =
        api.uploadStatus(uploadId)

    suspend fun uploadChunkMultipart(
        uploadId: String,
        chunkIndex: Int,
        chunkFile: File
    ): ChunkUploadResponse {
        val uploadIdBody = uploadId.toRequestBody("text/plain".toMediaType())
        val chunkIndexBody = chunkIndex.toString().toRequestBody("text/plain".toMediaType())
        val chunkBody = chunkFile.asRequestBody("application/octet-stream".toMediaType())
        val part = MultipartBody.Part.createFormData("chunk", chunkFile.name, chunkBody)
        return api.uploadChunkMultipart(uploadIdBody, chunkIndexBody, part)
    }

    suspend fun completeUpload(uploadId: String, filename: String): CompleteUploadResponse =
        api.completeUpload(
            com.swimanalysis.app.data.model.CompleteUploadRequest(uploadId, filename)
        )

    suspend fun cancelUpload(uploadId: String) =
        api.cancelUpload(com.swimanalysis.app.data.model.CancelUploadRequest(uploadId))

    suspend fun startAnalyze(
        taskId: String,
        swimmerName: String,
        poolLength: Int,
        raceDistance: Int,
        strokeType: String,
        analysisOptions: List<String>
    ) = api.startAnalyze(
        taskId,
        com.swimanalysis.app.data.model.AnalyzeRequest(
            swimmerName, poolLength, raceDistance, strokeType, analysisOptions
        )
    )

    suspend fun analyzeProgress(taskId: String): AnalyzeProgressResponse =
        api.analyzeProgress(taskId)

    suspend fun analyzeResult(taskId: String) = api.analyzeResult(taskId)

    suspend fun parseAnalysisResult(taskId: String): AnalysisResult {
        val resp = api.analyzeResult(taskId)
        val resultElement = resp["result"]
            ?: resp["analysis_result"]
            ?: resp["_meta"]
        return AnalysisResult.fromJson(
            resultElement?.let {
                kotlinx.serialization.json.Json.parseToJsonElement(it.toString())
            }
        )
    }

    suspend fun archiveRecord(
        taskId: String,
        raceName: String,
        raceDate: String,
        raceLocation: String
    ) = api.archiveRecord(
        taskId,
        com.swimanalysis.app.data.model.ArchiveRequest(raceName, raceDate, raceLocation)
    )

    suspend fun getRecords(swimmerName: String): List<RecordDto> =
        api.getRecords(swimmerName)

    suspend fun getAllRecords(): List<RecordDto> = api.getAllRecords()

    suspend fun compareRecords(id1: String, id2: String) = api.compareRecords(id1, id2)

    suspend fun getCompetitions(): List<CompetitionDto> = api.getCompetitions()

    suspend fun createCompetition(name: String, date: String?, location: String?): CompetitionDto =
        api.createCompetition(
            com.swimanalysis.app.data.model.CompetitionCreateRequest(name, date, location)
        )

    suspend fun deleteCompetition(compId: String) = api.deleteCompetition(compId)

    suspend fun getVideos(): List<VideoDto> = api.getVideosFromDb()

    suspend fun getMarkers(videoId: String): List<MarkerDto> = api.getMarkers(videoId)

    suspend fun addMarker(
        videoId: String,
        timeSeconds: Double,
        label: String,
        color: String,
        markerKey: String
    ): MarkerDto = api.addMarker(
        videoId,
        com.swimanalysis.app.data.model.MarkerCreateRequest(timeSeconds, label, color, markerKey)
    )

    suspend fun deleteMarker(videoId: String, markerId: String) =
        api.deleteMarker(videoId, markerId)

    suspend fun detectStartSignal(videoId: String) = api.detectStartSignal(videoId)

    suspend fun recognizeImage(imageFile: File): Map<String, Any> {
        val mediaType = "image/jpeg".toMediaType()
        val body = imageFile.asRequestBody(mediaType)
        val part = MultipartBody.Part.createFormData("image", imageFile.name, body)
        return api.recognizeImage(part)
    }

    suspend fun recognizeCompetition(imageFile: File): Map<String, Any> {
        val mediaType = "image/jpeg".toMediaType()
        val body = imageFile.asRequestBody(mediaType)
        val part = MultipartBody.Part.createFormData("image", imageFile.name, body)
        return api.recognizeCompetition(part)
    }

    suspend fun compareEvaluate(recordIds: List<String>, swimmerName: String) =
        api.compareEvaluate(
            com.swimanalysis.app.data.model.CompareEvaluateRequest(recordIds, swimmerName)
        )
}