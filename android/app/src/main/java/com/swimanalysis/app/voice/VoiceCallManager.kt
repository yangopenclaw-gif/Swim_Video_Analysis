package com.swimanalysis.app.voice

import android.content.Context
import android.util.Log
import com.ss.bytertc.engine.RTCRoom
import com.ss.bytertc.engine.RTCRoomConfig
import com.ss.bytertc.engine.RTCEngine
import com.ss.bytertc.engine.UserInfo
import com.ss.bytertc.engine.data.EngineConfig
import com.ss.bytertc.engine.data.StreamInfo
import com.ss.bytertc.engine.handler.IRTCEngineEventHandler
import com.ss.bytertc.engine.handler.IRTCRoomEventHandler
import com.ss.bytertc.engine.type.ChannelProfile
import com.ss.bytertc.engine.type.RoomState
import com.ss.bytertc.engine.type.RoomStateChangeReason
import com.swimanalysis.app.BuildConfig
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.nio.ByteBuffer
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

sealed class VoiceEvent {
    data object Connected : VoiceEvent()
    data object Disconnected : VoiceEvent()
    data class BotJoined(val uid: String) : VoiceEvent()
    data class BotAudioPublished(val uid: String) : VoiceEvent()
    data class Subtitle(val text: String, val fromBot: Boolean, val definite: Boolean) : VoiceEvent()
    data class Error(val message: String) : VoiceEvent()
}

@Singleton
class VoiceCallManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    private var engine: RTCEngine? = null
    private var room: RTCRoom? = null
    private var botUid: String? = null
    private var diagTaskId: String? = null

    private val _events = MutableSharedFlow<VoiceEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<VoiceEvent> = _events

    private val diagClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .writeTimeout(8, TimeUnit.SECONDS)
        .build()

    val isActive: Boolean get() = room != null

    fun start(appId: String, roomId: String, userId: String, token: String, botUserId: String, taskId: String) {
        if (engine != null || appId.isBlank() || token.isBlank()) return
        botUid = botUserId
        diagTaskId = taskId
        diag("engine_start", "appId=${appId.take(8)}… room=$roomId user=$userId bot=$botUserId")
        try {
            val config = EngineConfig()
            config.context = context
            config.appID = appId
            engine = RTCEngine.createRTCEngine(config, engineHandler)
            engine?.startAudioCapture()
            diag("engine_created", "audioCapture started")
            val rtcRoom = engine?.createRTCRoom(roomId)
            room = rtcRoom
            rtcRoom?.setRTCRoomEventHandler(roomHandler)
            val userInfo = UserInfo(userId, "")
            val roomConfig = RTCRoomConfig(
                ChannelProfile.CHANNEL_PROFILE_COMMUNICATION,
                null,
                true, false, true, false
            )
            rtcRoom?.joinRoom(token, userInfo, true, roomConfig)
            diag("joinRoom_invoked", "profile=COMMUNICATION autoPubAudio=true autoSubAudio=true")
        } catch (e: Exception) {
            diag("engine_exception", Log.getStackTraceString(e).take(800))
            _events.tryEmit(VoiceEvent.Error("语音引擎启动失败：${e.message}"))
            stop()
        }
    }

    fun stop() {
        try {
            room?.leaveRoom()
            room?.destroy()
        } catch (_: Exception) {
        }
        room = null
        try {
            RTCEngine.destroyRTCEngine()
        } catch (_: Exception) {
        }
        engine = null
    }

    private fun diag(event: String, detail: String) {
        val task = diagTaskId ?: return
        GlobalScope.launch(Dispatchers.IO) {
            try {
                val json = JSONObject().apply {
                    put("task_id", task)
                    put("event", event)
                    put("detail", detail.take(1000))
                }
                val body = json.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url("${BuildConfig.SERVER_BASE_URL}/api/voice/diag")
                    .post(body)
                    .build()
                diagClient.newCall(request).execute().close()
            } catch (_: Exception) {
            }
        }
    }

    private val engineHandler = object : IRTCEngineEventHandler() {
        override fun onError(err: Int) {
            super.onError(err)
            diag("engine_error", "code=$err")
            _events.tryEmit(VoiceEvent.Error("RTC 错误码 $err"))
        }

        override fun onWarning(warn: Int) {
            super.onWarning(warn)
            diag("engine_warning", "code=$warn")
        }
    }

    private val roomHandler = object : IRTCRoomEventHandler() {
        override fun onRoomStateChangedWithReason(
            roomId: String?, uid: String?, state: RoomState?, reason: RoomStateChangeReason?
        ) {
            super.onRoomStateChangedWithReason(roomId, uid, state, reason)
            diag("room_state", "state=$state reason=$reason")
            when (state) {
                RoomState.JOIN_SUCCESS -> _events.tryEmit(VoiceEvent.Connected)
                RoomState.JOIN_FAILED -> _events.tryEmit(
                    VoiceEvent.Error("进房失败（$reason），请重试")
                )
                RoomState.LEFT -> _events.tryEmit(VoiceEvent.Disconnected)
                else -> {}
            }
        }

        override fun onUserJoined(userInfo: UserInfo?) {
            super.onUserJoined(userInfo)
            val uid = userInfo?.uid ?: return
            diag("user_joined", "uid=$uid isBot=${uid == botUid}")
            if (uid == botUid) {
                _events.tryEmit(VoiceEvent.BotJoined(uid))
            }
        }

        override fun onUserPublishStreamAudio(streamId: String?, streamInfo: StreamInfo?, isPublish: Boolean) {
            super.onUserPublishStreamAudio(streamId, streamInfo, isPublish)
            val uid = streamInfo?.userId ?: ""
            diag("user_audio", "uid=$uid isPublish=$isPublish")
            if (isPublish && uid == botUid) {
                _events.tryEmit(VoiceEvent.BotAudioPublished(uid))
            }
        }

        override fun onLeaveRoom(stats: com.ss.bytertc.engine.type.RTCRoomStats?) {
            super.onLeaveRoom(stats)
            diag("leave_room", "stats=${stats?.toString()?.take(200)}")
            _events.tryEmit(VoiceEvent.Disconnected)
        }

        override fun onRoomBinaryMessageReceived(uid: String?, message: ByteBuffer?) {
            super.onRoomBinaryMessageReceived(uid, message)
            if (message == null) return
            val map = parseBinaryMessage(message)
            if (map["event"] != "subtitle") {
                if (map.isNotEmpty()) diag("binary_msg", "uid=$uid keys=${map.keys} raw=${map.toString().take(300)}")
                return
            }
            val text = map["text"] ?: return
            if (text.isBlank()) return
            val fromBot = uid == botUid
            val definite = map["definite"] == "true"
            _events.tryEmit(VoiceEvent.Subtitle(text, fromBot, definite))
        }
    }

    private fun parseBinaryMessage(message: ByteBuffer): Map<String, String> {
        val map = mutableMapOf<String, String>()
        try {
            val bytes = ByteArray(message.remaining())
            message.get(bytes)
            var offset = 0
            fun readU16(): Int {
                val v = (bytes[offset].toInt() and 0xFF) or ((bytes[offset + 1].toInt() and 0xFF) shl 8)
                offset += 2
                return v
            }
            while (offset + 2 <= bytes.size) {
                val keyLen = readU16()
                if (keyLen <= 0 || offset + keyLen > bytes.size) break
                val key = String(bytes, offset, keyLen, Charsets.UTF_8)
                offset += keyLen
                if (offset + 2 > bytes.size) break
                val valLen = readU16()
                if (offset + valLen > bytes.size) break
                val value = String(bytes, offset, valLen, Charsets.UTF_8)
                offset += valLen
                map[key] = value
            }
        } catch (_: Exception) {
        }
        return map
    }
}