package com.swimanalysis.app.album

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.PointF
import android.media.ExifInterface
import android.media.FaceDetector
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import kotlin.math.atan2
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

    override fun equals(other: Any?): Boolean = this === other
    override fun hashCode(): Int = embedding.contentHashCode()
}

class FaceRecognizer {

    companion object {
        private const val FACE_SIZE = 64
        private const val MAX_IMAGE_DIM = 640
        private const val MATCH_THRESHOLD = 0.55f
        private const val STRICT_THRESHOLD = 0.62f
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

            val faceBitmap = if (count > 0) {
                val face = faces.filterNotNull().maxByOrNull { it.confidence() }!!
                val midPoint = PointF()
                face.getMidPoint(midPoint)
                val eyeDist = face.eyesDistance()
                alignAndCropFace(scaled, midPoint, eyeDist)
            } else {
                centerCrop(scaled)
            }

            rgb565.recycle()
            scaled.recycle()

            if (faceBitmap == null) return@withContext null

            val embedding = extractFaceEmbedding(faceBitmap)
            faceBitmap.recycle()

            FaceFeature(embedding, if (count > 0) faces.filterNotNull().maxByOrNull { it.confidence() }!!.confidence() else 0.5f)
        } catch (e: Exception) {
            null
        }
    }

    fun averageFeatures(features: List<FaceFeature>): FaceFeature? {
        if (features.isEmpty()) return null
        val size = features[0].embedding.size
        val avg = FloatArray(size)
        for (f in features) {
            val e = f.embedding
            for (i in 0 until size) avg[i] += e[i]
        }
        val count = features.size.toFloat()
        for (i in 0 until size) avg[i] = avg[i] / count
        val avgConf = features.map { it.confidence }.average().toFloat()
        return FaceFeature(normalize(avg), avgConf)
    }

    fun saveFeature(file: File, feature: FaceFeature) {
        DataOutputStream(file.outputStream()).use {
            it.writeFloat(feature.confidence)
            it.writeInt(feature.embedding.size)
            for (v in feature.embedding) it.writeFloat(v)
        }
    }

    fun loadFeature(file: File): FaceFeature? {
        return try {
            DataInputStream(file.inputStream()).use { dis ->
                val confidence = dis.readFloat()
                val size = dis.readInt()
                if (size <= 0 || size > 100000) return null
                val embedding = FloatArray(size) { dis.readFloat() }
                FaceFeature(embedding, confidence)
            }
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

        val leftEyeX = midPoint.x - eyeDist / 2f
        val leftEyeY = midPoint.y
        val standardEyeDist = FACE_SIZE * 0.4f
        val scale = standardEyeDist / eyeDist

        val matrix = Matrix()
        matrix.postTranslate(-leftEyeX, -leftEyeY)
        matrix.postScale(scale, scale)
        matrix.postTranslate(FACE_SIZE * 0.3f, FACE_SIZE * 0.4f)

        val aligned = Bitmap.createBitmap(FACE_SIZE, FACE_SIZE, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(aligned)
        canvas.drawColor(Color.BLACK)
        val paint = Paint(Paint.FILTER_BITMAP_FLAG)
        canvas.drawBitmap(bitmap, matrix, paint)
        return aligned
    }

    private fun centerCrop(bitmap: Bitmap): Bitmap? {
        val w = bitmap.width
        val h = bitmap.height
        val size = minOf(w, h) * 70 / 100
        if (size < 20) return null
        val left = (w - size) / 2
        val top = (h - size) / 2
        val cropped = Bitmap.createBitmap(bitmap, left, top, size, size)
        val resized = Bitmap.createScaledBitmap(cropped, FACE_SIZE, FACE_SIZE, true)
        if (cropped !== resized) cropped.recycle()
        return resized
    }

    private fun extractFaceEmbedding(faceBitmap: Bitmap): FloatArray {
        val size = FACE_SIZE * FACE_SIZE
        val pixels = IntArray(size)
        faceBitmap.getPixels(pixels, 0, FACE_SIZE, 0, 0, FACE_SIZE, FACE_SIZE)

        val gray = IntArray(size) { grayValue(pixels[it]).toInt().coerceIn(0, 255) }
        val equalized = histogramEqualizeInt(gray)
        val lbp = computeLBPImage(equalized)
        val lbph = computeLBPH(lbp)
        val grayHist = computeGrayBlockHist(equalized)
        val hog = computeHOG(equalized)

        val embedding = FloatArray(lbph.size + grayHist.size + hog.size)
        var idx = 0
        for (v in lbph) embedding[idx++] = v
        for (v in grayHist) embedding[idx++] = v * 0.3f
        for (v in hog) embedding[idx++] = v * 0.5f
        return normalize(embedding)
    }

    private fun histogramEqualizeInt(gray: IntArray): IntArray {
        val hist = IntArray(256)
        for (v in gray) hist[v]++
        val cdf = IntArray(256)
        cdf[0] = hist[0]
        for (i in 1 until 256) cdf[i] = cdf[i - 1] + hist[i]
        val cdfMin = cdf.first { it > 0 }
        val total = gray.size
        val lut = IntArray(256)
        for (i in 0 until 256) {
            lut[i] = ((cdf[i] - cdfMin).toFloat() / (total - cdfMin) * 255f).toInt().coerceIn(0, 255)
        }
        return IntArray(total) { i -> lut[gray[i]] }
    }

    private fun computeLBPImage(gray: IntArray): IntArray {
        val w = FACE_SIZE
        val h = FACE_SIZE
        val lbp = IntArray(w * h)
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val c = gray[y * w + x]
                var code = 0
                if (gray[(y - 1) * w + (x - 1)] >= c) code = code or 1
                if (gray[(y - 1) * w + x] >= c) code = code or 2
                if (gray[(y - 1) * w + (x + 1)] >= c) code = code or 4
                if (gray[y * w + (x + 1)] >= c) code = code or 8
                if (gray[(y + 1) * w + (x + 1)] >= c) code = code or 16
                if (gray[(y + 1) * w + x] >= c) code = code or 32
                if (gray[(y + 1) * w + (x - 1)] >= c) code = code or 64
                if (gray[y * w + (x - 1)] >= c) code = code or 128
                lbp[y * w + x] = code
            }
        }
        return lbp
    }

    private fun computeLBPH(lbp: IntArray): FloatArray {
        val blocks = 4
        val blockW = FACE_SIZE / blocks
        val blockH = FACE_SIZE / blocks
        val hist = FloatArray(blocks * blocks * 256)
        for (by in 0 until blocks) {
            for (bx in 0 until blocks) {
                val offset = (by * blocks + bx) * 256
                var count = 0
                for (y in by * blockH until (by + 1) * blockH) {
                    for (x in bx * blockW until (bx + 1) * blockW) {
                        hist[offset + (lbp[y * FACE_SIZE + x] and 0xFF)]++
                        count++
                    }
                }
                if (count > 0) for (i in 0 until 256) hist[offset + i] /= count.toFloat()
            }
        }
        return hist
    }

    private fun computeGrayBlockHist(gray: IntArray): FloatArray {
        val blocks = 4
        val blockW = FACE_SIZE / blocks
        val blockH = FACE_SIZE / blocks
        val bins = 16
        val hist = FloatArray(blocks * blocks * bins)
        for (by in 0 until blocks) {
            for (bx in 0 until blocks) {
                val offset = (by * blocks + bx) * bins
                var count = 0
                for (y in by * blockH until (by + 1) * blockH) {
                    for (x in bx * blockW until (bx + 1) * blockW) {
                        val v = gray[y * FACE_SIZE + x].coerceIn(0, 255)
                        hist[offset + v * bins / 256]++
                        count++
                    }
                }
                if (count > 0) for (i in 0 until bins) hist[offset + i] /= count.toFloat()
            }
        }
        return hist
    }

    private fun computeHOG(gray: IntArray): FloatArray {
        val w = FACE_SIZE
        val h = FACE_SIZE
        val bins = 9
        val blocks = 4
        val blockW = w / blocks
        val blockH = h / blocks
        val hist = FloatArray(blocks * blocks * bins)

        val magnitude = FloatArray(w * h)
        val orientation = FloatArray(w * h)
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val gx = (gray[y * w + (x + 1)] - gray[y * w + (x - 1)]).toFloat()
                val gy = (gray[(y + 1) * w + x] - gray[(y - 1) * w + x]).toFloat()
                magnitude[y * w + x] = sqrt(gx * gx + gy * gy)
                var angle = atan2(gy, gx) * 180f / Math.PI.toFloat()
                if (angle < 0) angle += 180f
                orientation[y * w + x] = angle
            }
        }

        for (by in 0 until blocks) {
            for (bx in 0 until blocks) {
                val offset = (by * blocks + bx) * bins
                for (y in by * blockH until (by + 1) * blockH) {
                    for (x in bx * blockW until (bx + 1) * blockW) {
                        val bin = (orientation[y * w + x] / 180f * bins).toInt().coerceIn(0, bins - 1)
                        hist[offset + bin] += magnitude[y * w + x]
                    }
                }
                var sum = 0f
                for (i in 0 until bins) sum += hist[offset + i] * hist[offset + i]
                sum = sqrt(sum)
                if (sum > 0) for (i in 0 until bins) hist[offset + i] /= sum
            }
        }
        return hist
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

    fun isMatch(feature1: FaceFeature, feature2: FaceFeature, threshold: Float = MATCH_THRESHOLD): Boolean {
        return feature1.cosineSimilarity(feature2) > threshold
    }

    fun isStrictMatch(feature1: FaceFeature, feature2: FaceFeature, threshold: Float = STRICT_THRESHOLD): Boolean {
        return feature1.cosineSimilarity(feature2) > threshold
    }
}
