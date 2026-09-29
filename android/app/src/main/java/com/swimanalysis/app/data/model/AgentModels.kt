package com.swimanalysis.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AgentChatRequest(
    val message: String,
    @SerialName("conversation_id") val conversationId: String? = null
)

@Serializable
data class ChatEvent(
    val type: String = "",
    val text: String = "",
    val name: String = "",
    @SerialName("conversation_id") val conversationId: String? = null
)

@Serializable
data class ConversationDto(
    val id: String = "",
    val title: String = "",
    @SerialName("updated_at") val updatedAt: String? = null
)

@Serializable
data class ConversationListResponse(
    val items: List<ConversationDto> = emptyList()
)

@Serializable
data class ChatMessageDto(
    val role: String = "",
    val content: String = ""
)

@Serializable
data class MessageListResponse(
    val items: List<ChatMessageDto> = emptyList()
)

@Serializable
data class ScheduleDto(
    val id: String = "",
    val title: String = "",
    val content: String = "",
    @SerialName("remind_at") val remindAt: String = "",
    val repeat: String = "none"
)

@Serializable
data class ScheduleListResponse(
    val items: List<ScheduleDto> = emptyList()
)

@Serializable
data class ScheduleCreateRequest(
    val title: String,
    val content: String = "",
    @SerialName("remind_at") val remindAt: String,
    val repeat: String = "none"
)

@Serializable
data class DocumentDto(
    val id: String = "",
    val title: String = "",
    @SerialName("chunk_count") val chunkCount: Int = 0,
    @SerialName("created_at") val createdAt: String? = null
)

@Serializable
data class DocumentListResponse(
    val items: List<DocumentDto> = emptyList()
)

@Serializable
data class KbUploadRequest(
    val title: String,
    val content: String
)

@Serializable
data class KbUploadResponse(
    val status: String = "",
    val id: String = "",
    @SerialName("chunk_count") val chunkCount: Int = 0
)
@Serializable
data class NoteDto(
    val id: String = "",
    val title: String = "",
    val content: String = "",
    val date: String = "",
    @SerialName("created_at") val createdAt: String? = null
)

@Serializable
data class NoteListResponse(
    val items: List<NoteDto> = emptyList()
)

@Serializable
data class NoteCreateRequest(
    val title: String,
    val content: String = "",
    val date: String = ""
)
@Serializable
data class ImageExtractResponse(
    val status: String = "",
    val text: String = ""
)
@Serializable
data class DocParseResponse(
    val status: String = "",
    val text: String = "",
    val filename: String = ""
)
@Serializable
data class UploadFileResponse(
    val status: String = "",
    @SerialName("file_id") val fileId: String = "",
    val filename: String = ""
)