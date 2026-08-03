package com.swimanalysis.app.album

import android.content.Context
import android.location.Geocoder
import android.media.ExifInterface
import android.net.Uri
import android.provider.MediaStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class PersonPhoto(
    val uri: Uri,
    val path: String,
    val dateTaken: Long,
    val dateText: String,
    val location: String?,
    val size: Long
)

data class PersonAlbum(
    val name: String,
    val referenceFeatures: List<FaceFeature>,
    val photos: List<PersonPhoto>
) {
    val photoCount: Int get() = photos.size
}

data class ScanState(
    val status: ScanStatus = ScanStatus.IDLE,
    val progress: Float = 0f,
    val currentPhoto: String = "",
    val totalCount: Int = 0,
    val scannedCount: Int = 0,
    val albums: Map<String, PersonAlbum> = emptyMap(),
    val error: String? = null
)

enum class ScanStatus { IDLE, SCANNING, COMPLETED, FAILED }

class PhotoScanner(
    private val context: Context,
    private val faceRecognizer: FaceRecognizer
) {

    fun scanAlbums(
        personNames: List<String>,
        referenceUris: Map<String, List<Uri>>
    ): Flow<ScanState> = flow {
        var state = ScanState(status = ScanStatus.SCANNING, totalCount = 0)
        emit(state)

        try {
            val referenceFeatures = mutableMapOf<String, List<FaceFeature>>()
            for (name in personNames) {
                val uris = referenceUris[name] ?: emptyList()
                val features = uris.mapNotNull { uri ->
                    faceRecognizer.extractFeature(context, uri)
                }
                referenceFeatures[name] = features
                state = state.copy(
                    progress = 0.1f,
                    currentPhoto = "已注册 $name 的 ${features.size} 张参考照片"
                )
                emit(state)
            }

            val allPhotos = queryAllPhotos()
            state = state.copy(totalCount = allPhotos.size, progress = 0.15f)
            emit(state)

            val classifiedPhotos = mutableMapOf<String, MutableList<PersonPhoto>>()
            for (name in personNames) {
                classifiedPhotos[name] = mutableListOf()
            }

            for ((index, photo) in allPhotos.withIndex()) {
                state = state.copy(
                    scannedCount = index + 1,
                    progress = 0.15f + 0.85f * (index + 1) / allPhotos.size,
                    currentPhoto = "扫描 ${index + 1}/${allPhotos.size}: ${photo.path.substringAfterLast('/')}"
                )
                emit(state)

                val feature = faceRecognizer.extractFeature(context, photo.uri)
                if (feature == null) continue

                for (name in personNames) {
                    val refs = referenceFeatures[name] ?: continue
                    val matched = refs.any { ref -> faceRecognizer.isMatch(ref, feature) }
                    if (matched) {
                        classifiedPhotos[name]!!.add(photo)
                        break
                    }
                }
            }

            val albums = mutableMapOf<String, PersonAlbum>()
            for (name in personNames) {
                val sortedPhotos = classifiedPhotos[name]!!.sortedByDescending { it.dateTaken }
                albums[name] = PersonAlbum(
                    name = name,
                    referenceFeatures = referenceFeatures[name] ?: emptyList(),
                    photos = sortedPhotos
                )
            }

            emit(state.copy(
                status = ScanStatus.COMPLETED,
                progress = 1f,
                currentPhoto = "扫描完成",
                albums = albums
            ))
        } catch (e: Exception) {
            emit(state.copy(status = ScanStatus.FAILED, error = e.message))
        }
    }.flowOn(Dispatchers.IO)

    private fun queryAllPhotos(): List<PersonPhoto> {
        val photos = mutableListOf<PersonPhoto>()
        val projection = arrayOf(
            MediaStore.Images.Media._ID,
            MediaStore.Images.Media.DATA,
            MediaStore.Images.Media.DATE_TAKEN,
            MediaStore.Images.Media.SIZE,
            MediaStore.Images.Media.LATITUDE,
            MediaStore.Images.Media.LONGITUDE,
            MediaStore.Images.Media.DISPLAY_NAME
        )
        val sortOrder = "${MediaStore.Images.Media.DATE_TAKEN} DESC"
        val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.CHINA)

        context.contentResolver.query(
            MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
            projection,
            null,
            null,
            sortOrder
        )?.use { cursor ->
            val idCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media._ID)
            val dataCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATA)
            val dateCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATE_TAKEN)
            val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.SIZE)
            val latCol = cursor.getColumnIndex(MediaStore.Images.Media.LATITUDE)
            val lngCol = cursor.getColumnIndex(MediaStore.Images.Media.LONGITUDE)
            val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DISPLAY_NAME)

            while (cursor.moveToNext()) {
                val id = cursor.getLong(idCol)
                val path = cursor.getString(dataCol) ?: continue
                val dateTaken = cursor.getLong(dateCol)
                val size = cursor.getLong(sizeCol)
                val name = cursor.getString(nameCol)
                val lat = if (latCol >= 0) cursor.getDouble(latCol) else 0.0
                val lng = if (lngCol >= 0) cursor.getDouble(lngCol) else 0.0

                val uri = Uri.withAppendedPath(
                    MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                    id.toString()
                )

                val dateText = if (dateTaken > 0) dateFormat.format(Date(dateTaken)) else "未知时间"
                val location = getLocationFromExif(path, lat, lng)

                photos.add(PersonPhoto(uri, path, dateTaken, dateText, location, size))
            }
        }
        return photos
    }

    private fun getLocationFromExif(path: String, lat: Double, lng: Double): String? {
        var latitude = lat
        var longitude = lng

        if (latitude == 0.0 || longitude == 0.0) {
            try {
                val exif = ExifInterface(path)
                val latLng = DoubleArray(2)
                if (exif.getLatLong(latLng)) {
                    latitude = latLng[0]
                    longitude = latLng[1]
                }
            } catch (_: Exception) {}
        }

        if (latitude == 0.0 || longitude == 0.0) return null

        return try {
            val geocoder = Geocoder(context, Locale.CHINA)
            val addresses = geocoder.getFromLocation(latitude, longitude, 1)
            if (addresses != null && addresses.isNotEmpty()) {
                val addr = addresses[0]
                listOfNotNull(
                    addr.locality,
                    addr.subLocality,
                    addr.thoroughfare
                ).joinToString(" ").ifEmpty { null }
            } else null
        } catch (_: Exception) {
            "%.4f, %.4f".format(latitude, longitude)
        }
    }
}