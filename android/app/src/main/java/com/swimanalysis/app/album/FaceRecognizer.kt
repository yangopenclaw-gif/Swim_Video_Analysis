package com.swimanalysis.app.album

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.PointF
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

    companion object {
        private const val FACE_SIZE = 48
        private const val MAX_IMAGE_DIM = 640
    }

    suspend fun extractFeature(context: Context, uri: Uri): FaceFeature? = withContext(Dispatchers.IO) {
        try {
            val bitmap = loadBitmap(context, uri) ?: return@withContext null
            val scaled = scaleDownIfNeeded(bitmap)
            if (scaled !== bitmap) bitmap.recycle()

            val rgb565 = scaled.copy(Bitmap.Config.RGB_565, false)
            if (rgb565 == null) {
                scaled.recycle()
                return@withContext null
            }

            val maxFaces = 5
            val faces = arrayOfNulls<FaceDetector.Face>(maxFaces)
            val detector = FaceDetector(rgb565.width, rgb565.height, maxFaces)
            val count = detector.findFaces(rgb565, faces)

            if (count == 0) {
                rgb565.recycle()
                scaled.recycle()
                return@withContext null
            }

            val face = faces.filterNotNull().maxByOrNull { it.confidence() }!!
            val midPoint = PointF()
            face.getMidPoint(midPoint)
            val eyeDist = face.eyesDistance()

            val faceBitmap = alignAndCropFace(scaled, midPoint, eyeDist)

            rgb565.recycle()
            scaled.recycle()

            if (faceBitmap == null) return@withContext null

            val embedding = extractFaceEmbedding(faceBitmap)
            faceBitmap.recycle()

            FaceFeature(embedding, face.confidence())
        } catch (e: Exception) {
            null
        }
    }

    private fun scaleDownIfNeeded(bitmap: Bitmap): Bitmap {
        val maxDim = maxOf(bitmap.width, bitmap.height)
        if (maxDim <= MAX_IMAGE_DIM) return bitmap
        val scale = MAX_IMAGE_DIM.toFloat() / maxDim
        return Bitmap.createScaledBitmap(
            bitmap,
            (bitmap.width * scale).toInt(),
            (bitmap.height * scale).toInt(),
            true
        )
    }

    private fun alignAndCropFace(bitmap: Bitmap, midPoint: PointF, eyeDist: Float): Bitmap? {
        if (eyeDist < 10f) return null

        val faceWidth = eyeDist * 2.2f
        val faceHeight = eyeDist * 2.8f

        val srcLeft = (midPoint.x - faceWidth / 2).coerceAtLeast(0f).toInt()
        val srcTop = (midPoint.y - faceHeight * 0.35f).coerceAtLeast(0f).toInt()
        val srcRight = (midPoint.x + faceWidth / 2).coerceAtMost(bitmap.width.toFloat()).toInt()
        val srcBottom = (midPoint.y + faceHeight * 0.65f).coerceAtMost(bitmap.height.toFloat()).toInt()

        val w = srcRight - srcLeft
        val h = srcBottom - srcTop
        if (w < 20 || h < 20) return null

        val cropped = Bitmap.createBitmap(bitmap, srcLeft, srcTop, w, h)
        val resized = Bitmap.createScaledBitmap(cropped, FACE_SIZE, FACE_SIZE, true)
        if (cropped !== resized) cropped.recycle()
        return resized
    }

    private fun extractFaceEmbedding(faceBitmap: Bitmap): FloatArray {
        val size = FACE_SIZE * FACE_SIZE
        val pixels = IntArray(size)
        faceBitmap.getPixels(pixels, 0, FACE_SIZE, 0, 0, FACE_SIZE, FACE_SIZE)

        val gray = FloatArray(size)
        var mean = 0f
        for (i in pixels.indices) {
            val lum = grayValue(pixels[i])
            gray[i] = lum
            mean += lum
        }
        mean /= size

        var std = 0f
        for (i in gray.indices) {
            gray[i] -= mean
            std += gray[i] * gray[i]
        }
        std = sqrt(std / size)
        if (std > 0.1f) {
            for (i in gray.indices) {
                gray[i] /= std
            }
        }

        val lbp = computeLBP(pixels)

        val embedding = FloatArray(size + lbp.size)
        System.arraycopy(gray, 0, embedding, 0, size)
        for (i in lbp.indices) {
            embedding[size + i] = lbp[i] * 0.5f
        }

        return normalize(embedding)
    }

    private fun computeLBP(pixels: IntArray): FloatArray {
        val w = FACE_SIZE
        val h = FACE_SIZE
        val lbp = FloatArray(w * h)

        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val center = grayValue(pixels[y * w + x])
                var code = 0
                if (grayValue(pixels[(y - 1) * w + (x - 1)]) >= center) code = code or 1
                if (grayValue(pixels[(y - 1) * w + x]) >= center) code = code or 2
                if (grayValue(pixels[(y - 1) * w + (x + 1)]) >= center) code = code or 4
                if (grayValue(pixels[y * w + (x + 1)]) >= center) code = code or 8
                if (grayValue(pixels[(y + 1) * w + (x + 1)]) >= center) code = code or 16
                if (grayValue(pixels[(y + 1) * w + x]) >= center) code = code or 32
                if (grayValue(pixels[(y + 1) * w + (x - 1)]) >= center) code = code or 64
                if (grayValue(pixels[y * w + (x - 1)]) >= center) code = code or 128
                lbp[y * w + x] = code.toFloat() / 255f
            }
        }
        return lbp
    }

    private fun grayValue(pixel: Int): Float {
        val r = Color.red(pixel)
        val g = Color.green(pixel)
        val b = Color.blue(pixel)
        return 0.299f * r + 0.587f * g + 0.114f * b
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
            val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            if (rotated !== bitmap) bitmap.recycle()
            rotated
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

    fun isMatch(feature1: FaceFeature, feature2: FaceFeature, threshold: Float = 0.55f): Boolean {
        return feature1.cosineSimilarity(feature2) > threshold
    }
}
