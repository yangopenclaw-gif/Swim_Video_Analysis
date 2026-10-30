package com.swimanalysis.app.voice

import android.content.Context
import com.ss.bytertc.engine.RTCRoom
import com.ss.bytertc.engine.RTCRoomConfig
import com.ss.bytertc.engine.RTCEngine
import com.ss.bytertc.engine.UserInfo
import com.ss.bytertc.engine.data.EngineConfig
import com.ss.bytertc.engine.data.StreamInfo
import com.ss.bytertc.engine.handler.IRTCEngineEventHandler
import com.ss.bytertc.engine.handler.IRTCRoomEventHandler
import com.ss.bytertc.engine.type.ChannelProfile
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import java.nio.ByteBuffer
import javax.inject.Inject
import javax.inject.Singleton

sealed class VoiceEvent {
    data object Connected : VoiceEvent()
    data object Disconnected : VoiceEvent()
    data class BotJoined(val uid: String) : VoiceEvent()
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

    private val _events = MutableSharedFlow<VoiceEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<VoiceEvent> = _events

    val isActive: Boolean get() = room != null

    fun start(appId: String, roomId: String, userId: String, token: String, botUserId: String) {
        if (engine != null || appId.isBlank() || token.isBlank()) return
        botUid = botUserId
        val config = EngineConfig()
        config.context = context
        config.appID = appId
        engine = RTCEngine.createRTCEngine(config, engineHandler)
        engine?.startAudioCapture()
        val rtcRoom = engine?.createRTCRoom(roomId)
        room = rtcRoom
        rtcRoom?.setRTCRoomEventHandler(roomHandler)
        val userInfo = UserInfo(userId, "")
        val roomConfig = RTCRoomConfig(
            ChannelProfile.CHANNEL_PROFILE_CHAT_ROOM,
            null,
            true, false, true, false
        )
        rtcRoom?.joinRoom(token, userInfo, true, roomConfig)
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

    private val engineHandler = object : IRTCEngineEventHandler() {
        override fun onError(err: Int) {
            super.onError(err)
            _events.tryEmit(VoiceEvent.Error("RTC 错误码 $err"))
        }
    }

    private val roomHandler = object : IRTCRoomEventHandler() {
        override fun onRoomStateChanged(roomId: String?, uid: String?, state: Int, extraInfo: String?) {
            super.onRoomStateChanged(roomId, uid, state, extraInfo)
            when (state) {
                0 -> _events.tryEmit(VoiceEvent.Connected)
                3 -> _events.tryEmit(VoiceEvent.Disconnected)
            }
        }

        override fun onUserJoined(userInfo: UserInfo?) {
            super.onUserJoined(userInfo)
            val uid = userInfo?.uid ?: return
            if (uid == botUid) {
                _events.tryEmit(VoiceEvent.BotJoined(uid))
            }
        }

        override fun onUserPublishStreamAudio(streamId: String?, streamInfo: StreamInfo?, isPublish: Boolean) {
            super.onUserPublishStreamAudio(streamId, streamInfo, isPublish)
        }

        override fun onLeaveRoom(stats: com.ss.bytertc.engine.type.RTCRoomStats?) {
            super.onLeaveRoom(stats)
            _events.tryEmit(VoiceEvent.Disconnected)
        }

        override fun onRoomBinaryMessageReceived(uid: String?, message: ByteBuffer?) {
            super.onRoomBinaryMessageReceived(uid, message)
            if (message == null) return
            val map = parseBinaryMessage(message)
            if (map["event"] != "subtitle") return
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