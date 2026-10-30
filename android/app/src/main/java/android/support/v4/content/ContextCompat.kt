package android.support.v4.content

import android.content.Context

/**
 * 火山 RTC SDK 内部引用旧 support 库的 ContextCompat 检查麦克风权限。
 * 依赖已 exclude(com.android.support)，若无 Jetifier 改写则运行时
 * NoClassDefFoundError——此桩将调用桥接到 androidx 等价实现兜底。
 */
@Suppress("unused")
class ContextCompat private constructor() {
    companion object {
        @JvmStatic
        fun checkSelfPermission(context: Context, permission: String): Int =
            androidx.core.content.ContextCompat.checkSelfPermission(context, permission)
    }
}