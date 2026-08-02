package com.swimanalysis.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class UploadInitRequest(
    val filename: String,
    val file_size: Long,
    @SerialName("athlete_name") val athleteName: String = "",
    @SerialName("display_name") val displayName: String = "",
    @SerialName("competition_name") val competitionName: String = ""
)

@Serializable
data class UploadInitResponse(
    @SerialName("upload_id") val uploadId: String,
    @SerialName("chunk_size") val chunkSize: Int,
    @SerialName("total_chunks") val totalChunks: Int,
    val filename: String = ""
)

@Serializable
data class UploadStatusResponse(
    @SerialName("upload_id") val uploadId: String,
    @SerialName("chunks_received") val chunksReceived: List<Int> = emptyList(),
    @SerialName("total_chunks") val totalChunks: Int = 0,
    @SerialName("file_size") val fileSize: Long = 0L,
    val filename: String = "",
    @SerialName("missing_chunks") val missingChunks: List<Int> = emptyList()
)

@Serializable
data class ChunkUploadRequest(
    @SerialName("upload_id") val uploadId: String,
    @SerialName("chunk_index") val chunkIndex: Int,
    val data: String
)

@Serializable
data class ChunkUploadResponse(
    val success: Boolean = true,
    @SerialName("chunk_index") val chunkIndex: Int = 0,
    @SerialName("received_chunks") val receivedChunks: Int = 0,
    @SerialName("total_chunks") val totalChunks: Int = 0
)

@Serializable
data class CompleteUploadRequest(
    @SerialName("upload_id") val uploadId: String,
    val filename: String
)

@Serializable
data class CompleteUploadResponse(
    @SerialName("task_id") val taskId: String = "",
    @SerialName("video_id") val videoId: String = "",
    val filename: String = "",
    @SerialName("file_size") val fileSize: Long = 0L
)

@Serializable
data class CancelUploadRequest(
    @SerialName("upload_id") val uploadId: String
)

@Serializable
data class AnalyzeRequest(
    @SerialName("swimmer_name") val swimmerName: String,
    @SerialName("pool_length") val poolLength: Int = 50,
    @SerialName("race_distance") val raceDistance: Int = 50,
    @SerialName("stroke_type") val strokeType: String = "自由泳",
    @SerialName("analysis_options") val analysisOptions: List<String> = emptyList()
)

@Serializable
data class AnalyzeExistingRequest(
    @SerialName("swimmer_name") val swimmerName: String = "",
    @SerialName("pool_length") val poolLength: Int = 50,
    @SerialName("race_distance") val raceDistance: Int = 50,
    @SerialName("stroke_type") val strokeType: String = "自由泳",
    @SerialName("analysis_options") val analysisOptions: List<String> = emptyList()
)

@Serializable
data class AnalyzeProgressResponse(
    @SerialName("task_id") val taskId: String = "",
    val status: String = "pending",
    val progress: Int = 0,
    val message: String = "",
    val result: JsonElement? = null
)

@Serializable
data class ArchiveRequest(
    @SerialName("race_name") val raceName: String,
    @SerialName("race_date") val raceDate: String = "",
    @SerialName("race_location") val raceLocation: String = ""
)

@Serializable
data class RecordDto(
    val id: String = "",
    @SerialName("swimmer_name") val swimmerName: String = "",
    @SerialName("pool_length") val poolLength: Int = 0,
    @SerialName("race_distance") val raceDistance: Int = 0,
    @SerialName("stroke_type") val strokeType: String = "",
    @SerialName("swimmer_position") val swimmerPosition: Int = 0,
    @SerialName("video_filename") val videoFilename: String? = null,
    @SerialName("analysis_result") val analysisResult: String = "",
    @SerialName("created_at") val createdAt: String = "",
    val archived: Boolean = false,
    @SerialName("archive_time") val archiveTime: String? = null,
    @SerialName("race_name") val raceName: String? = null,
    @SerialName("race_date") val raceDate: String? = null,
    @SerialName("race_location") val raceLocation: String? = null,
    @SerialName("video_deleted") val videoDeleted: Boolean = false,
    @SerialName("linked_video_id") val linkedVideoId: String? = null
)

@Serializable
data class CompareTimelineRequest(
    @SerialName("record_ids") val recordIds: List<String>
)

@Serializable
data class SwimmerProfileDto(
    val name: String = "",
    @SerialName("birth_date") val birthDate: String? = null,
    val gender: String? = null,
    val notes: String? = null,
    @SerialName("avatar_url") val avatarUrl: String? = null
)

@Serializable
data class SwimmerProfileUpdate(
    @SerialName("birth_date") val birthDate: String? = null,
    val gender: String? = null,
    val notes: String? = null
)

@Serializable
data class CompetitionDto(
    val id: String = "",
    val name: String = "",
    val date: String? = null,
    val location: String? = null,
    @SerialName("created_at") val createdAt: String = ""
)

@Serializable
data class CompetitionCreateRequest(
    val name: String,
    val date: String? = null,
    val location: String? = null
)

@Serializable
data class CompetitionUpdateRequest(
    val name: String? = null,
    val date: String? = null,
    val location: String? = null
)

@Serializable
data class DuplicateCheckRequest(
    @SerialName("swimmer_name") val swimmerName: String,
    @SerialName("race_name") val raceName: String,
    @SerialName("race_distance") val raceDistance: Int,
    @SerialName("stroke_type") val strokeType: String
)

@Serializable
data class ManualRecordRequest(
    @SerialName("swimmer_name") val swimmerName: String,
    @SerialName("pool_length") val poolLength: Int = 50,
    @SerialName("race_distance") val raceDistance: Int,
    @SerialName("stroke_type") val strokeType: String,
    @SerialName("swimmer_position") val swimmerPosition: Int = 0,
    @SerialName("race_name") val raceName: String = "",
    @SerialName("race_date") val raceDate: String = "",
    @SerialName("race_location") val raceLocation: String = "",
    @SerialName("total_time") val totalTime: String,
    @SerialName("linked_video_id") val linkedVideoId: String? = null
)

@Serializable
data class RecordUpdateRequest(
    val password: String,
    @SerialName("swimmer_name") val swimmerName: String? = null,
    @SerialName("pool_length") val poolLength: Int? = null,
    @SerialName("race_distance") val raceDistance: Int? = null,
    @SerialName("stroke_type") val strokeType: String? = null,
    @SerialName("swimmer_position") val swimmerPosition: Int? = null,
    @SerialName("analysis_result") val analysisResult: String? = null
)

@Serializable
data class DeleteRequest(
    val password: String
)

@Serializable
data class VideoFsDto(
    val name: String = "",
    val size: Long = 0L,
    val path: String = "",
    @SerialName("analyzed") val analyzed: Boolean = false,
    @SerialName("task_id") val taskId: String? = null
)

@Serializable
data class VideoDto(
    val id: String = "",
    @SerialName("file_name") val fileName: String = "",
    @SerialName("display_name") val displayName: String = "",
    @SerialName("athlete_name") val athleteName: String = "",
    @SerialName("athlete_id") val athleteId: String? = null,
    @SerialName("competition_name") val competitionName: String? = null,
    @SerialName("competition_id") val competitionId: String? = null,
    @SerialName("upload_time") val uploadTime: String = "",
    @SerialName("file_size") val fileSize: Long = 0L,
    val duration: Double = 0.0,
    @SerialName("linked_record_id") val linkedRecordId: String? = null
)

@Serializable
data class VideoUpdateRequest(
    val password: String,
    @SerialName("display_name") val displayName: String? = null,
    @SerialName("athlete_name") val athleteName: String? = null,
    @SerialName("competition_name") val competitionName: String? = null
)

@Serializable
data class MarkerDto(
    val id: String = "",
    @SerialName("video_id") val videoId: String = "",
    @SerialName("time_seconds") val timeSeconds: Double = 0.0,
    val label: String = "",
    val color: String = "#FF0000",
    @SerialName("marker_key") val markerKey: String = "",
    @SerialName("created_at") val createdAt: String = ""
)

@Serializable
data class MarkerCreateRequest(
    @SerialName("time_seconds") val timeSeconds: Double,
    val label: String,
    val color: String = "#FF0000",
    @SerialName("marker_key") val markerKey: String = ""
)

@Serializable
data class CalculateRequest(
    @SerialName("start_time") val startTime: Double,
    @SerialName("end_time") val endTime: Double,
    @SerialName("turn_time") val turnTime: Double? = null,
    @SerialName("pool_length") val poolLength: Int = 50,
    @SerialName("race_distance") val raceDistance: Int = 50
)

@Serializable
data class SaveMarkerResultRequest(
    @SerialName("swimmer_name") val swimmerName: String,
    @SerialName("pool_length") val poolLength: Int = 50,
    @SerialName("race_distance") val raceDistance: Int = 50,
    @SerialName("stroke_type") val strokeType: String = "自由泳",
    @SerialName("result") val result: Map<String, Any>
)

@Serializable
data class LinkRecordRequest(
    @SerialName("record_id") val recordId: String
)

@Serializable
data class CompareEvaluateRequest(
    @SerialName("record_ids") val recordIds: List<String>,
    @SerialName("swimmer_name") val swimmerName: String = ""
)