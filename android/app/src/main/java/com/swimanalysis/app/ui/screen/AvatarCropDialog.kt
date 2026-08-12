package com.swimanalysis.app.ui.screen

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gesture.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.round
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.math.max
import kotlin.math.min

@Composable
fun AvatarCropDialog(
    imageUri: Uri,
    onConfirm: (Bitmap) -> Unit,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    var sourceBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var loadFailed by remember { mutableStateOf(false) }

    LaunchedEffect(imageUri) {
        sourceBitmap = null
        loadFailed = false
        val bmp = withContext(Dispatchers.IO) {
            try {
                val input = context.contentResolver.openInputStream(imageUri) ?: return@withContext null
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeStream(input, null, bounds)
                input.close()
                val maxDim = max(bounds.outWidth, bounds.outHeight)
                var sample = 1
                while (maxDim / sample > 1280) sample *= 2
                val input2 = context.contentResolver.openInputStream(imageUri) ?: return@withContext null
                val opts = BitmapFactory.Options().apply { inSampleSize = sample }
                val decoded = BitmapFactory.decodeStream(input2, null, opts)
                input2.close()
                decoded?.let { correctRotation(context, imageUri, it) }
            } catch (e: Exception) {
                null
            }
        }
        if (bmp != null) sourceBitmap = bmp else loadFailed = true
    }

    val bitmap = sourceBitmap
    if (bitmap == null) {
        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text("裁剪头像") },
            text = {
                if (loadFailed) Text("图片加载失败") else Text("正在加载图片...")
            },
            confirmButton = {},
            dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }
        )
        return
    }

    var scale by remember { mutableFloatStateOf(1f) }
    var offsetX by remember { mutableFloatStateOf(0f) }
    var offsetY by remember { mutableFloatStateOf(0f) }
    var range by remember { mutableFloatStateOf(0.8f) }

    val density = LocalDensity.current
    val boxPx = with(density) { 300.dp.toPx() }
    val iw = bitmap.width.toFloat()
    val ih = bitmap.height.toFloat()
    val fitW: Float
    val fitH: Float
    if (iw / ih > 1f) {
        fitW = boxPx
        fitH = boxPx * ih / iw
    } else {
        fitH = boxPx
        fitW = boxPx * iw / ih
    }
    val dispLeft = (boxPx - fitW) / 2f
    val dispTop = (boxPx - fitH) / 2f

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("裁剪头像") },
        text = {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(
                    modifier = Modifier
                        .size(300.dp)
                        .background(Color.Black),
                    contentAlignment = Alignment.Center
                ) {
                    Image(
                        bitmap = bitmap.asImageBitmap(),
                        contentDescription = "待裁剪图片",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier
                            .fillMaxSize()
                            .graphicsLayerSafe(scale, offsetX, offsetY)
                            .pointerInput(Unit) {
                                detectTransformGestures { _, pan, zoom, _ ->
                                    scale = (scale * zoom).coerceIn(0.5f, 6f)
                                    offsetX += pan.x
                                    offsetY += pan.y
                                }
                            }
                    )
                    Box(
                        modifier = Modifier
                            .size((300 * range).dp)
                            .clip(CircleShape)
                            .background(Color.Transparent),
                        contentAlignment = Alignment.Center
                    ) {}
                    Box(
                        modifier = Modifier
                            .size((300 * range).dp)
                            .clip(CircleShape)
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(Color.Transparent),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                "裁剪区",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.White
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                Text("双指缩放、单指拖动调整；滑块控制裁剪范围", style = MaterialTheme.typography.bodySmall)
                Slider(
                    value = range,
                    onValueChange = { range = it.coerceIn(0.4f, 1f) },
                    valueRange = 0.4f..1f
                )
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val cropped = cropCircle(
                    bitmap, boxPx, iw, ih, fitW, fitH, dispLeft, dispTop,
                    scale, offsetX, offsetY, range
                )
                onConfirm(cropped)
            }) { Text("确定") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }
    )
}

private fun Modifier.graphicsLayerSafe(scale: Float, tx: Float, ty: Float): Modifier =
    this.then(
        androidx.compose.ui.graphics.graphicsLayer(
            scaleX = scale, scaleY = scale,
            translationX = tx, translationY = ty
        )
    )

private fun cropCircle(
    bitmap: Bitmap, boxPx: Float, iw: Float, ih: Float,
    fitW: Float, fitH: Float, dispLeft: Float, dispTop: Float,
    scale: Float, offsetX: Float, offsetY: Float, range: Float
): Bitmap {
    val center = boxPx / 2f
    val screenRadius = (boxPx * range) / 2f
    val sxToDisp = (center - center - offsetX) / scale + center
    val syToDisp = (center - center - offsetY) / scale + center
    val srcCx = ((sxToDisp - dispLeft) * (iw / fitW)).coerceIn(0f, iw)
    val srcCy = ((syToDisp - dispTop) * (ih / fitH)).coerceIn(0f, ih)
    val srcRadius = screenRadius * (iw / fitW) / scale
    var side = (srcRadius * 2f).coerceAtLeast(8f)
    var left = (srcCx - side / 2f).toInt()
    var top = (srcCy - side / 2f).toInt()
    var right = (left + side.toInt())
    var bottom = (top + side.toInt())
    if (left < 0) { right -= left; left = 0 }
    if (top < 0) { bottom -= top; top = 0 }
    if (right > iw.toInt()) { left -= (right - iw.toInt()); right = iw.toInt() }
    if (bottom > ih.toInt()) { top -= (bottom - ih.toInt()); bottom = ih.toInt() }
    left = max(0, left); top = max(0, top)
    right = min(iw.toInt(), right); bottom = min(ih.toInt(), bottom)
    side = min(right - left, bottom - top).toFloat().coerceAtLeast(8f)
    val cropped = Bitmap.createBitmap(bitmap, left, top, side.toInt(), side.toInt())
    val outputSize = 256
    val scaled = Bitmap.createScaledBitmap(cropped, outputSize, outputSize, true)
    if (cropped !== scaled) cropped.recycle()
    return scaled
}

private fun correctRotation(context: android.content.Context, uri: Uri, bitmap: Bitmap): Bitmap {
    return try {
        val input = context.contentResolver.openInputStream(uri) ?: return bitmap
        val exif = androidx.exifinterface.media.ExifInterface(input)
        input.close()
        val rotation = when (exif.getAttributeInt(
            androidx.exifinterface.media.ExifInterface.TAG_ORIENTATION,
            androidx.exifinterface.media.ExifInterface.ORIENTATION_NORMAL
        )) {
            androidx.exifinterface.media.ExifInterface.ORIENTATION_ROTATE_90 -> 90
            androidx.exifinterface.media.ExifInterface.ORIENTATION_ROTATE_180 -> 180
            androidx.exifinterface.media.ExifInterface.ORIENTATION_ROTATE_270 -> 270
            else -> 0
        }
        if (rotation == 0) bitmap
        else {
            val matrix = Matrix().apply { postRotate(rotation.toFloat()) }
            val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            if (rotated !== bitmap) bitmap.recycle()
            rotated
        }
    } catch (e: Exception) {
        bitmap
    }
}

