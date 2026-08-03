package com.swimanalysis.app.ui.navigation

sealed class Screen(val route: String, val title: String) {
    data object Home : Screen("home", "首页")
    data object Records : Screen("records", "记录")
    data object Upload : Screen("upload", "上传")
    data object Videos : Screen("videos", "视频")
    data object Album : Screen("album", "相册")
    data object Profile : Screen("profile", "我的")

    data object RecordDetail : Screen("record/{recordId}", "记录详情")
    data object VideoPlayer : Screen("video/{videoId}", "视频播放")
    data object VideoAnnotate : Screen("annotate/{videoId}", "视频标注")
    data object AnalyzeProgress : Screen("analyze/{taskId}", "分析进度")
    data object Compare : Screen("compare", "记录对比")
    data object Competitions : Screen("competitions", "比赛管理")
    data object AiRecognize : Screen("ai_recognize", "AI识别")
    data object SwimmerProfile : Screen("swimmer/{name}", "泳者档案")
    data object Settings : Screen("settings", "设置")

    fun withArgs(vararg args: String): String {
        return buildString {
            append(route.substringBefore("/"))
            args.forEach { append("/").append(it) }
        }
    }
}