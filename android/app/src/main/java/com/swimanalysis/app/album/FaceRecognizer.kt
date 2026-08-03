package com.swimanalysis.app.album

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.Face
import com.google.mlkit.vision.face.FaceContour
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.face.FaceLandmark
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import kotlin.math.sqrt

data class FaceFeature(
    val embedding: FloatArray,
    val bounds: android.graphics.Rect
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

    private val detector = FaceDetection.getClient(
        FaceDetectorOptions.Builder()
            .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
            .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
            .setContourMode(FaceDetectorOptions.CONTOUR_MODE_ALL)
            .setClassificationMode(FaceDetectorOptions.CLASSIFICATION_MODE_ALL)
            .setMinFaceSize(0.15f)
            .build()
    )

    suspend fun detectFaces(bitmap: Bitmap): List<Face> = suspendCancellableCoroutine { cont ->
        val image = InputImage.fromBitmap(bitmap, 0)
        detector.process(image)
            .addOnSuccessListener { faces -> cont.resume(faces) }
            .addOnFailureListener { cont.resume(emptyList()) }
    }

    suspend fun extractFeature(context: Context, uri: Uri): FaceFeature? = withContext(Dispatchers.IO) {
        try {
            val bitmap = loadBitmap(context, uri) ?: return@withContext null
            val faces = detectFaces(bitmap)
            if (faces.isEmpty()) return@withContext null

            val face = faces.maxByOrNull { it.boundingBox.width() * it.boundingBox.height() }!!
            val embedding = computeEmbedding(face)
            FaceFeature(embedding, face.boundingBox)
        } catch (e: Exception) {
            null
        }
    }

    private fun computeEmbedding(face: Face): FloatArray {
        val features = mutableListOf<Float>()

        val leftEye = face.getLandmark(FaceLandmark.LEFT_EYE)
        features.add(leftEye?.position?.x ?: 0f)
        features.add(leftEye?.position?.y ?: 0f)

        val rightEye = face.getLandmark(FaceLandmark.RIGHT_EYE)
        features.add(rightEye?.position?.x ?: 0f)
        features.add(rightEye?.position?.y ?: 0f)

        val nose = face.getLandmark(FaceLandmark.NOSE_BASE)
        features.add(nose?.position?.x ?: 0f)
        features.add(nose?.position?.y ?: 0f)

        val mouthLeft = face.getLandmark(FaceLandmark.MOUTH_LEFT)
        features.add(mouthLeft?.position?.x ?: 0f)
        features.add(mouthLeft?.position?.y ?: 0f)

        val mouthRight = face.getLandmark(FaceLandmark.MOUTH_RIGHT)
        features.add(mouthRight?.position?.x ?: 0f)
        features.add(mouthRight?.position?.y ?: 0f)

        val leftEar = face.getLandmark(FaceLandmark.LEFT_EAR)
        features.add(leftEar?.position?.x ?: 0f)
        features.add(leftEar?.position?.y ?: 0f)

        val rightEar = face.getLandmark(FaceLandmark.RIGHT_EAR)
        features.add(rightEar?.position?.x ?: 0f)
        features.add(rightEar?.position?.y ?: 0f)

        features.add(face.headEulerAngleX)
        features.add(face.headEulerAngleY)
        features.add(face.headEulerAngleZ)
        features.add(face.smilingProbability ?: 0f)
        features.add(face.leftEyeOpenProbability ?: 0f)
        features.add(face.rightEyeOpenProbability ?: 0f)

        val contour = face.getContour(FaceContour.FACE)
        contour?.points?.forEach { p ->
            features.add(p.x); features.add(p.y)
        }

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

    fun isMatch(feature1: FaceFeature, feature2: FaceFeature, threshold: Float = 0.82f): Boolean {
        return feature1.cosineSimilarity(feature2) > threshold
    }
}
