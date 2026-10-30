# Retrofit
-keepattributes Signature
-keepattributes *Annotation*
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep interface okhttp3.** { *; }

# Kotlinx Serialization
-keepattributes RuntimeVisibleAnnotations,AnnotationDefault
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class com.swimanalysis.app.**$$serializer { *; }
-keepclassmembers class com.swimanalysis.app.** {
    *** Companion;
}
-keepclasseswithmembers class com.swimanalysis.app.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Hilt
-keep class dagger.hilt.** { *; }
-keep class javax.inject.** { *; }
-keep class * extends dagger.hilt.android.internal.modules.ApplicationContextModule { *; }

# Media3 / ExoPlayer
-keep class androidx.media3.** { *; }
-dontwarn androidx.media3.**

# CameraX
-keep class androidx.camera.** { *; }
-dontwarn androidx.camera.**

# Compose
-keep class androidx.compose.** { *; }
# VolcEngineRTC：厂商可选接口(荣耀等)为 compileOnly，运行时按机型反射可用性探测
-dontwarn com.hihonor.android.magicx.**
-dontwarn com.ss.bytertc.**
# 对齐官方 APIExample keep 清单：SDK 内部 JNI/反射依赖这些包的原始类名，
# 缺一即 native 崩溃(SIGSEGV)——Java try-catch 无法捕获
-keep class com.ss.bytertc.** { *; }
-keep class com.bytedance.** { *; }
-keep class com.ss.** { *; }
-keep class com.pandora.** { *; }
-keep class log.** { *; }