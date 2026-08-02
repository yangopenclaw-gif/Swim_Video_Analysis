package com.swimanalysis.app.upload

import com.swimanalysis.app.data.repository.SwimRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import java.io.File
import java.io.RandomAccessFile
import javax.inject.Inject
import javax.inject.Singleton

data class UploadState(
    val uploadId: String = "",
    val totalChunks: Int = 0,
    val uploadedChunks: Int = 0,
    val progress: Float = 0f,
    val status: UploadStatus = UploadStatus.IDLE,
    val message: String = "",
    val taskId: String = "",
    val videoId: String = ""
)

enum class UploadStatus { IDLE, INIT, UPLOADING, COMPLETING, SUCCESS, FAILED, PAUSED }

@Singleton
class ChunkUploader @Inject constructor(
    private val repository: SwimRepository
) {
    companion object {
        const val CHUNK_SIZE = 512 * 1024
    }

    fun upload(
        file: File,
        athleteName: String,
        displayName: String,
        competitionName: String
    ): Flow<UploadState> = flow {
        var state = UploadState(status = UploadStatus.INIT, message = "初始化上传...")
        emit(state)

        try {
            val initResp = repository.initUpload(
                filename = file.name,
                fileSize = file.length(),
                athleteName = athleteName,
                displayName = displayName,
                competitionName = competitionName
            )

            state = state.copy(
                uploadId = initResp.uploadId,
                totalChunks = initResp.totalChunks,
                status = UploadStatus.UPLOADING,
                message = "开始上传分片..."
            )
            emit(state)

            val statusResp = repository.uploadStatus(initResp.uploadId)
            val uploadedSet = statusResp.chunksReceived.toMutableSet()

            val raf = RandomAccessFile(file, "r")
            val buffer = ByteArray(CHUNK_SIZE)

            for (i in 0 until initResp.totalChunks) {
                if (uploadedSet.contains(i)) {
                    state = state.copy(
                        uploadedChunks = i + 1,
                        progress = (i + 1).toFloat() / initResp.totalChunks,
                        message = "分片 ${i + 1}/${initResp.totalChunks} (已存在)"
                    )
                    emit(state)
                    continue
                }

                raf.seek(i.toLong() * CHUNK_SIZE)
                val readLen = raf.read(buffer)
                val chunkFile = File.createTempFile("chunk_${i}_", ".bin")
                chunkFile.writeBytes(buffer.copyOf(readLen))

                try {
                    repository.uploadChunkMultipart(initResp.uploadId, i, chunkFile)
                    uploadedSet.add(i)
                } finally {
                    chunkFile.delete()
                }

                state = state.copy(
                    uploadedChunks = i + 1,
                    progress = (i + 1).toFloat() / initResp.totalChunks,
                    message = "分片 ${i + 1}/${initResp.totalChunks} 上传完成"
                )
                emit(state)
            }

            raf.close()

            state = state.copy(status = UploadStatus.COMPLETING, message = "合并分片...")
            emit(state)

            val completeResp = repository.completeUpload(initResp.uploadId, file.name)

            state = state.copy(
                status = UploadStatus.SUCCESS,
                taskId = completeResp.taskId,
                videoId = completeResp.videoId,
                progress = 1f,
                message = "上传完成"
            )
            emit(state)

        } catch (e: Exception) {
            emit(state.copy(status = UploadStatus.FAILED, message = "上传失败: ${e.message}"))
        }
    }.flowOn(Dispatchers.IO)
}