package com.swimanalysis.app.data.repository

import com.swimanalysis.app.BuildConfig
import com.swimanalysis.app.data.api.AgentApi
import com.swimanalysis.app.data.model.AgentChatRequest
import com.swimanalysis.app.data.model.ChatEvent
import com.swimanalysis.app.data.model.KbUploadRequest
import com.swimanalysis.app.data.model.ScheduleCreateRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AgentRepository @Inject constructor(
    private val api: AgentApi,
    private val client: OkHttpClient,
    private val json: Json
) {
    suspend fun listConversations() = api.listConversations().items

    suspend fun getMessages(id: String) = api.getMessages(id).items

    suspend fun listSchedules() = api.listSchedules().items

    suspend fun createSchedule(title: String, content: String, remindAt: String, repeat: String) =
        api.createSchedule(ScheduleCreateRequest(title, content, remindAt, repeat))

    suspend fun deleteSchedule(id: String) = api.deleteSchedule(id)

    suspend fun listDocuments() = api.listDocuments().items

    suspend fun uploadDocument(title: String, content: String) =
        api.uploadDocument(KbUploadRequest(title, content))

    suspend fun deleteDocument(id: String) = api.deleteDocument(id)

    fun streamChat(message: String, conversationId: String?): Flow<ChatEvent> = flow {
        val requestBody = json.encodeToString(AgentChatRequest(message, conversationId))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("${BuildConfig.SERVER_BASE_URL}/api/agent/chat")
            .post(requestBody)
            .build()
        val response = withContext(Dispatchers.IO) { client.newCall(request).execute() }
        if (!response.isSuccessful) {
            val err = response.body?.string() ?: "请求失败 ${response.code}"
            emit(ChatEvent(type = "error", text = err))
            response.close()
            return@flow
        }
        response.body?.use { body ->
            val source = body.source()
            while (!source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                if (line.startsWith("data:")) {
                    val payload = line.removePrefix("data:").trim()
                    if (payload.isNotEmpty() && payload != "[DONE]") {
                        try {
                            emit(json.decodeFromString(ChatEvent.serializer(), payload))
                        } catch (_: Exception) {
                            // 忽略无法解析的行
                        }
                    }
                }
            }
        }
        response.close()
    }
}