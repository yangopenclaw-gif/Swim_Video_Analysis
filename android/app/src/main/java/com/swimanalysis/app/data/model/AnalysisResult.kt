package com.swimanalysis.app.data.model

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

data class AnalysisResult(
    val totalTime: String = "",
    val firstHalfTime: String = "",
    val secondHalfTime: String = "",
    val firstHalfStrokes: Int = 0,
    val secondHalfStrokes: Int = 0,
    val firstHalfBreaths: Int = 0,
    val secondHalfBreaths: Int = 0,
    val firstHalfKicks: Int = 0,
    val secondHalfKicks: Int = 0,
    val turnTime: String = "",
    val strokeRate: String = "",
    val pace: String = "",
    val raw: Map<String, JsonElement> = emptyMap()
) {
    companion object {
        fun fromJson(element: JsonElement?): AnalysisResult {
            if (element == null) return AnalysisResult()
            val obj = (element as? JsonObject) ?: return AnalysisResult()
            val raw = obj.toMap()

            fun str(key: String): String =
                (obj[key] as? JsonPrimitive)?.contentOrNull ?: ""

            fun int(key: String): Int? =
                (obj[key] as? JsonPrimitive)?.intOrNull

            fun dbl(key: String): Double? =
                (obj[key] as? JsonPrimitive)?.doubleOrNull

            return AnalysisResult(
                totalTime = str("比赛总用时").ifEmpty { str("总用时") },
                firstHalfTime = str("第1半程用时").ifEmpty { str("前程用时") },
                secondHalfTime = str("第2半程用时").ifEmpty { str("后程用时") },
                firstHalfStrokes = int("第1半程划水次数") ?: int("前程划水次数") ?: 0,
                secondHalfStrokes = int("第2半程划水次数") ?: int("后程划水次数") ?: 0,
                firstHalfBreaths = int("第1半程换气次数") ?: int("前程换气次数") ?: 0,
                secondHalfBreaths = int("第2半程换气次数") ?: int("后程换气次数") ?: 0,
                firstHalfKicks = int("第1半程打腿次数") ?: int("前程打腿次数") ?: 0,
                secondHalfKicks = int("第2半程打腿次数") ?: int("后程打腿次数") ?: 0,
                turnTime = str("转身出水用时").ifEmpty { str("转身用时") },
                strokeRate = str("划水频率").ifEmpty { str("平均划频") },
                pace = str("平均配速"),
                raw = raw
            )
        }
    }
}