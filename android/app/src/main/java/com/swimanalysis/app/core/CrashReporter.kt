package com.swimanalysis.app.core

import android.content.Context
import android.os.Build
import com.swimanalysis.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

object CrashReporter {

    private const val DIR_NAME = "crash"
    private var appContext: Context? = null

    fun install(context: Context) {
        appContext = context.applicationContext
        val dir = File(context.filesDir, DIR_NAME)
        if (!dir.exists()) dir.mkdirs()

        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                writeCrashFile(dir, thread.name, throwable)
            } catch (_: Exception) {
            }
            previous?.uncaughtException(thread, throwable)
        }
    }

    fun uploadPendingIfAny() {
        val context = appContext ?: return
        val dir = File(context.filesDir, DIR_NAME)
        val files = dir.listFiles { f -> f.name.endsWith(".json") } ?: return
        if (files.isEmpty()) return
        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .build()
        GlobalScope.launch(Dispatchers.IO) {
            for (f in files) {
                try {
                    val body = f.readText().toRequestBody("application/json".toMediaType())
                    val request = Request.Builder()
                        .url("${BuildConfig.SERVER_BASE_URL}/api/crash/report")
                        .post(body)
                        .build()
                    val resp = client.newCall(request).execute()
                    resp.close()
                    if (resp.isSuccessful) f.delete()
                } catch (_: Exception) {
                }
            }
        }
    }

    private fun writeCrashFile(dir: File, threadName: String, throwable: Throwable) {
        val ts = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.CHINA).format(Date())
        val stack = android.util.Log.getStackTraceString(throwable).take(12000)
        val json = JSONObject().apply {
            put("time", SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.CHINA).format(Date()))
            put("version", BuildConfig.VERSION_NAME)
            put("versionCode", BuildConfig.VERSION_CODE)
            put("android", Build.VERSION.RELEASE)
            put("model", Build.MANUFACTURER + " " + Build.MODEL)
            put("thread", threadName)
            put("stack", stack)
        }
        File(dir, "crash_$ts.json").writeText(json.toString())
    }
}