package com.swimanalysis.app.ui.screen.agent

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import java.util.Locale

class VoiceHelper(
    private val context: Context,
    private val onPartialResult: (String) -> Unit,
    private val onFinalResult: (String) -> Unit,
    private val onError: (String) -> Unit,
    private val onRms: (Float) -> Unit
) {
    private var speechRecognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false

    init {
        tts = TextToSpeech(context) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) {
                tts?.language = Locale.CHINESE
            }
        }
    }

    fun startListening() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            onError("当前设备不支持语音识别")
            return
        }
        releaseRecognizer()
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context).apply {
            setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {}
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) { onRms(rmsdB) }
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {}
                override fun onError(error: Int) {
                    releaseRecognizer()
                    onError(mapError(error))
                }

                override fun onResults(results: Bundle?) {
                    val text = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        .orEmpty()
                    releaseRecognizer()
                    if (text.isNotBlank()) onFinalResult(text)
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    val text = partialResults
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        .orEmpty()
                    if (text.isNotBlank()) onPartialResult(text)
                }

                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "zh-CN")
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        }
        speechRecognizer?.startListening(intent)
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
    }

    fun cancelListening() {
        speechRecognizer?.cancel()
        releaseRecognizer()
    }

    private fun releaseRecognizer() {
        speechRecognizer?.destroy()
        speechRecognizer = null
    }

    private fun mapError(code: Int): String = when (code) {
        SpeechRecognizer.ERROR_NO_MATCH -> "没听清，请按住再说一次"
        SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "没有听到声音，请按住说话"
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "缺少麦克风权限，请在系统设置中开启"
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "语音服务忙，请稍后再试"
        SpeechRecognizer.ERROR_NETWORK -> "网络异常，请检查网络后重试"
        SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "网络超时，请重试"
        SpeechRecognizer.ERROR_AUDIO -> "录音出错，请重试"
        SpeechRecognizer.ERROR_CLIENT -> "语音服务出错，请重试"
        SpeechRecognizer.ERROR_SERVER -> "语音服务端出错，请重试"
        else -> "识别失败（错误码 $code）"
    }

    fun speak(text: String) {
        if (ttsReady && text.isNotBlank()) {
            tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "agent_tts")
        }
    }

    fun stopSpeaking() {
        tts?.stop()
    }

    fun shutdown() {
        cancelListening()
        tts?.stop()
        tts?.shutdown()
        tts = null
    }
}