package com.swimanalysis.app.album

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Matrix
import android.media.ExifInterface
import android.media.FaceDetector
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.math.sqrt

data class FaceFeature(
    val embedding: FloatArray,
    val confidence: Float
) {
    fun cosineSimilarity(other: FaceFeature): Float {
        var dot = 0f
        var normA = 0f
        var normB = 0f
        for (i in embedding.indices) {
            dot += embedding[i] * other.embedding[i]
            normA += embedding[i] * embedding[i]
            normB += other.embedding[i] * other.embedding[i]
        }
        val denom = sqrt(normA) * sqrt(normB)
        return if (denom > 0) dot / denom else 0f
    }
}

class FaceRecognizer {

    suspend fun extractFeature(context: Context, uri: Uri): FaceFeature? = withContext(Dispatchers.IO) {
        try {
            val bitmap = loadBitmap(context, uri) ?: return@withContext null
            val rgb565 = bitmap.copy(Bitmap.Config.RGB_565, false)
            if (rgb565 == null) {
                bitmap.recycle()
                return@withContext null
            }

            val maxFaces = 5
            val faces = arrayOfNulls<FaceDetector.Face>(maxFaces)
            val detector = FaceDetector(rgb565.width, rgb565.height, maxFaces)
            val count = detector.findFaces(rgb565, faces)

            if (count == 0) {
                rgb565.recycle()
                bitmap.recycle()
                return@withContext null
            }

            val face = faces.filterNotNull().maxByOrNull { it.confidence() }!!
            val embedding = computeEmbedding(face, rgb565.width, rgb565.height)

            rgb565.recycle()
            bitmap.recycle()

            FaceFeature(embedding, face.confidence())
        } catch (e: Exception) {
            null
        }
    }

    private fun computeEmbedding(face: FaceDetector.Face, imgWidth: Int, imgHeight: Int): FloatArray {
        val features = mutableListOf<Float>()

        val eyeDist = face.eyesDistance()
        features.add(eyeDist / imgWidth)

        val midPoint = android.graphics.PointF()
        face.getMidPoint(midPoint)
        features.add(midPoint.x / imgWidth)
        features.add(midPoint.y / imgHeight)

        features.add(face.confidence())

        features.add(eyeDist / imgHeight)
        features.add(midPoint.x / imgHeight)
        features.add(midPoint.y / imgWidth)

        val eyeLeftX = midPoint.x - eyeDist / 2
        val eyeRightX = midPoint.x + eyeDist / 2
        features.add(eyeLeftX / imgWidth)
        features.add(eyeRightX / imgWidth)
        features.add(midPoint.y / imgHeight)

        features.add(eyeDist * eyeDist / (imgWidth * imgHeight))
        features.add(midPoint.x * midPoint.y / (imgWidth * imgHeight))

        return normalize(features.toFloatArray())
    }

    private fun normalize(arr: FloatArray): FloatArray {
        var norm = 0f
        for (v in arr) norm += v * v
        norm = sqrt(norm)
        return if (norm > 0) FloatArray(arr.size) { i -> arr[i] / norm } else arr
    }

    private suspend fun loadBitmap(context: Context, uri: Uri): Bitmap? = withContext(Dispatchers.IO) {
        try {
            val inputStream = context.contentResolver.openInputStream(uri) ?: return@withContext null
            val bitmap = BitmapFactory.decodeStream(inputStream)
            inputStream.close()
            if (bitmap == null) return@withContext null

            val rotation = getExifRotation(context, uri)
            if (rotation == 0) return@withContext bitmap

            val matrix = Matrix()
            matrix.postRotate(rotation.toFloat())
            Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        } catch (e: Exception) {
            null
        }
    }

    private fun getExifRotation(context: Context, uri: Uri): Int {
        return try {
            val inputStream = context.contentResolver.openInputStream(uri) ?: return 0
            val exif = ExifInterface(inputStream)
            inputStream.close()
            when (exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90
                ExifInterface.ORIENTATION_ROTATE_180 -> 180
                ExifInterface.ORIENTATION_ROTATE_270 -> 270
                else -> 0
            }
        } catch (e: Exception) {
            0
        }
    }

    fun isMatch(feature1: FaceFeature, feature2: FaceFeature, threshold: Float = 0.92f): Boolean {
        return feature1.cosineSimilarity(feature2) > threshold
    }
}
