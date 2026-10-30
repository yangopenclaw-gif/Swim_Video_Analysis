package com.swimanalysis.app.ui.screen.agent

import android.app.AlarmManager
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.swimanalysis.app.ui.theme.SwimAnalysisTheme
import kotlinx.coroutines.delay
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

class AlarmActivity : ComponentActivity() {

    private val scheduleId by lazy { intent.getStringExtra("id").orEmpty() }
    private val title by lazy { intent.getStringExtra("title") ?: "日程提醒" }
    private val content by lazy { intent.getStringExtra("content").orEmpty() }
    private var snoozed = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
            )
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enableEdgeToEdge()
        WindowCompat.getInsetsController(window, window.decorView).apply {
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            hide(WindowInsetsCompat.Type.systemBars())
        }
        setContent {
            SwimAnalysisTheme {
                AlarmScreen(
                    title = title,
                    content = content,
                    onDismiss = { finish() },
                    onSnooze = { snooze() }
                )
            }
        }
    }

    override fun onStart() {
        super.onStart()
        AlarmRinger.start(this)
    }

    override fun onStop() {
        super.onStop()
        AlarmRinger.stop()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (!snoozed) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.cancel(notifyId())
        }
    }

    private fun notifyId(): Int = scheduleId.ifBlank { title }.hashCode()

    private fun snooze() {
        snoozed = true
        val am = getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val pi = PendingIntent.getBroadcast(
            this, scheduleId.hashCode(),
            Intent(this, ScheduleReceiver::class.java).apply {
                putExtra("title", title)
                putExtra("content", content)
                putExtra("id", scheduleId)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        am.setWindow(
            AlarmManager.RTC_WAKEUP,
            System.currentTimeMillis() + SNOOZE_MINUTES * 60_000L,
            60_000L,
            pi
        )
        finish()
    }

    companion object {
        private const val SNOOZE_MINUTES = 9L
    }
}

@Composable
private fun AlarmScreen(
    title: String,
    content: String,
    onDismiss: () -> Unit,
    onSnooze: () -> Unit
) {
    var now by remember { mutableStateOf(LocalDateTime.now()) }
    LaunchedEffect(Unit) {
        while (true) {
            now = LocalDateTime.now()
            delay(1000)
        }
    }
    val timeText = remember(now) { now.format(DateTimeFormatter.ofPattern("HH:mm")) }
    val dateText = remember(now) {
        now.format(DateTimeFormatter.ofPattern("yyyy年M月d日 EEEE", Locale.CHINA))
    }
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(listOf(Color(0xFF16264F), Color(0xFF070B18)))
            )
            .padding(24.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(
                "⏰ 到点提醒",
                color = Color(0xFFFFB86B),
                fontSize = 16.sp,
                letterSpacing = 4.sp
            )
            Spacer(Modifier.height(12.dp))
            Text(
                timeText,
                color = Color.White,
                fontSize = 76.sp,
                fontWeight = FontWeight.Bold
            )
            Text(dateText, color = Color(0xFF9FB0D8), fontSize = 15.sp)
            Spacer(Modifier.height(40.dp))
            Text(
                title,
                color = Color.White,
                fontSize = 26.sp,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center
            )
            if (content.isNotBlank()) {
                Spacer(Modifier.height(10.dp))
                Text(
                    content,
                    color = Color(0xFFC7D2EE),
                    fontSize = 16.sp,
                    textAlign = TextAlign.Center
                )
            }
            Spacer(Modifier.height(72.dp))
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(28.dp)
            ) {
                SnoozeButton(onSnooze)
                DismissButton(onDismiss)
            }
        }
    }
}

@Composable
private fun DismissButton(onDismiss: () -> Unit) {
    Box(
        modifier = Modifier
            .size(84.dp)
            .background(
                Brush.verticalGradient(listOf(Color(0xFFFF9E5E), Color(0xFFF0722B))),
                CircleShape
            )
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null
            ) { onDismiss() },
        contentAlignment = Alignment.Center
    ) {
        Text("关闭", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun SnoozeButton(onSnooze: () -> Unit) {
    Box(
        modifier = Modifier
            .size(64.dp)
            .background(Color(0x26FFFFFF), CircleShape)
            .border(1.dp, Color(0x55FFFFFF), CircleShape)
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null
            ) { onSnooze() },
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("稍后", color = Color(0xFFDDA47A), fontSize = 14.sp)
            Text("9分钟", color = Color.White, fontSize = 12.sp)
        }
    }
}