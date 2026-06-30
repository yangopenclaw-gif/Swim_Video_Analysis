export interface UploadCallbacks {
  onProgress: (percent: number, uploadedBytes: number, totalBytes: number) => void
  onSpeed: (bytesPerSec: number) => void
  onEta: (seconds: number) => void
  onStatus: (text: string) => void
  onComplete: (taskId: string) => void
  onError: (message: string) => void
}

interface PendingUpload {
  uploadId: string
  filename: string
  fileSize: number
  totalChunks: number
  swimmerName: string
  poolLength: number
  raceDistance: number
  swimmerPosition: number
  createdAt: number
}

interface SpeedSample {
  time: number
  bytes: number
}

const API_BASE = '/api'
const CHUNK_SIZE = 4 * 1024 * 1024
const MAX_RETRIES = 3
const RETRY_DELAY_MS = 1500
const CONCURRENCY = 3
const STORAGE_KEY = 'swim_pending_uploads'
const UPLOAD_TTL_MS = 24 * 60 * 60 * 1000
const SPEED_WINDOW_SIZE = 6

export class VideoUploader {
  private abortController: AbortController | null = null
  private startTime = 0
  private uploadedBytes = 0
  private totalBytes = 0
  private completedChunks = 0
  private totalChunks = 0
  private cb: UploadCallbacks
  private currentUploadId: string | null = null
  private currentFile: File | null = null
  private paused = false
  private visibilityHandler: (() => void) | null = null
  private speedSamples: SpeedSample[] = []
  private lastReportTime = 0
  private chunkErrors = 0

  constructor(callbacks: UploadCallbacks) {
    this.cb = callbacks
    this.setupVisibilityListener()
  }

  destroy() {
    this.removeVisibilityListener()
  }

  private setupVisibilityListener() {
    this.visibilityHandler = () => {
      if (document.visibilityState === 'visible' && this.paused && this.currentUploadId && this.currentFile) {
        this.resumeUpload()
      }
    }
    document.addEventListener('visibilitychange', this.visibilityHandler)
  }

  private removeVisibilityListener() {
    if (this.visibilityHandler) {
      document.removeEventListener('visibilitychange', this.visibilityHandler)
      this.visibilityHandler = null
    }
  }

  cancel() {
    if (this.abortController) {
      this.abortController.abort()
      this.abortController = null
    }
    this.paused = false
    if (this.currentUploadId) {
      this.removePendingUpload(this.currentUploadId)
    }
    fetch(`${API_BASE}/upload/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: this.currentUploadId || '' }),
    }).catch(() => {})
  }

  async upload(
    file: File,
    swimmerName: string,
    poolLength: number,
    raceDistance: number,
    swimmerPosition: number,
  ) {
    this.currentFile = file
    this.abortController = new AbortController()
    this.totalBytes = file.size
    this.uploadedBytes = 0
    this.completedChunks = 0
    this.chunkErrors = 0
    this.startTime = Date.now()
    this.speedSamples = []
    this.lastReportTime = 0
    this.paused = false

    try {
      this.cb.onStatus('正在初始化上传...')
      this.cb.onProgress(0, 0, file.size)
      this.cb.onSpeed(0)
      this.cb.onEta(0)

      const uploadId = await this.initUpload(file, swimmerName, poolLength, raceDistance, swimmerPosition, this.abortController.signal)
      if (!uploadId) return

      this.currentUploadId = uploadId

      this.savePendingUpload({
        uploadId,
        filename: file.name,
        fileSize: file.size,
        totalChunks: this.totalChunks,
        swimmerName,
        poolLength,
        raceDistance,
        swimmerPosition,
        createdAt: Date.now(),
      })

      this.cb.onStatus(`正在上传分片 0/${this.totalChunks}...`)

      const ok = await this.uploadAllChunks(file, uploadId, this.abortController.signal)
      if (!ok) return

      this.cb.onStatus('正在合并文件...')
      this.cb.onProgress(100, file.size, file.size)
      this.cb.onSpeed(0)
      this.cb.onEta(0)

      const taskId = await this.completeUpload(uploadId, this.abortController.signal)
      if (!taskId) return

      this.removePendingUpload(uploadId)
      this.currentUploadId = null
      this.paused = false
      this.cb.onStatus('上传完成')
      this.cb.onComplete(taskId)
    } catch (err: any) {
      if (this.abortController?.signal.aborted) return
      this.paused = true
      this.cb.onError(err.message || '上传中断，请回到此页面自动续传')
    }
  }

  private async resumeUpload() {
    if (!this.currentUploadId || !this.currentFile) return

    this.paused = false
    this.speedSamples = []
    this.cb.onStatus('正在恢复上传...')

    try {
      const status = await this.queryUploadStatus(this.currentUploadId)
      if (!status) {
        this.cb.onError('上传会话已过期，请重新上传')
        this.removePendingUpload(this.currentUploadId)
        return
      }

      this.totalChunks = status.total_chunks
      const missingChunks = status.missing_chunks

      if (missingChunks.length === 0) {
        this.cb.onStatus('正在合并文件...')
        this.cb.onProgress(100, this.totalBytes, this.totalBytes)
        const taskId = await this.completeUpload(this.currentUploadId, this.getAbortSignal())
        if (taskId) {
          this.removePendingUpload(this.currentUploadId)
          this.currentUploadId = null
          this.cb.onStatus('上传完成')
          this.cb.onComplete(taskId)
        }
        return
      }

      this.completedChunks = status.received_chunks
      this.uploadedBytes = Math.min(this.completedChunks * CHUNK_SIZE, this.totalBytes)
      this.startTime = Date.now()
      this.speedSamples = []

      this.abortController = new AbortController()
      this.cb.onStatus(`正在续传分片 ${this.completedChunks}/${this.totalChunks}...`)

      const ok = await this.uploadMissingChunks(this.currentFile, this.currentUploadId, missingChunks, this.abortController.signal)
      if (!ok) return

      this.cb.onStatus('正在合并文件...')
      this.cb.onProgress(100, this.totalBytes, this.totalBytes)

      const taskId = await this.completeUpload(this.currentUploadId, this.abortController.signal)
      if (!taskId) return

      this.removePendingUpload(this.currentUploadId)
      this.currentUploadId = null
      this.cb.onStatus('上传完成')
      this.cb.onComplete(taskId)
    } catch (err: any) {
      this.paused = true
      this.cb.onError('恢复上传失败，请重试')
    }
  }

  private getAbortSignal(): AbortSignal {
    if (!this.abortController) {
      this.abortController = new AbortController()
    }
    return this.abortController.signal
  }

  private async queryUploadStatus(uploadId: string): Promise<{ received_chunks: number; total_chunks: number; missing_chunks: number[] } | null> {
    try {
      const res = await fetch(`${API_BASE}/upload/status/${encodeURIComponent(uploadId)}`)
      if (res.ok) return await res.json()
    } catch {}
    return null
  }

  private async initUpload(
    file: File,
    swimmerName: string,
    poolLength: number,
    raceDistance: number,
    swimmerPosition: number,
    signal: AbortSignal,
  ): Promise<string | null> {
    try {
      const res = await fetch(`${API_BASE}/upload/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          file_size: file.size,
          swimmer_name: swimmerName,
          pool_length: poolLength,
          race_distance: raceDistance,
          swimmer_position: swimmerPosition,
        }),
        signal,
      })
      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        this.cb.onError(`初始化上传失败 (${res.status}): ${errText}`)
        return null
      }
      const data = await res.json()
      this.totalChunks = data.total_chunks
      return data.upload_id
    } catch (err: any) {
      if (signal.aborted) return null
      this.cb.onError('初始化上传失败: ' + err.message)
      return null
    }
  }

  private async uploadChunk(
    uploadId: string,
    chunk: Blob,
    chunkIndex: number,
    signal: AbortSignal,
  ): Promise<'ok' | 'abort' | 'fail'> {
    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      if (signal.aborted) return 'abort'
      const chunkStart = Date.now()
      try {
        const res = await fetch(
          `${API_BASE}/upload/chunk?upload_id=${encodeURIComponent(uploadId)}&chunk_index=${chunkIndex}`,
          {
            method: 'POST',
            body: chunk,
            headers: { 'Content-Type': 'application/octet-stream' },
            signal,
          },
        )
        if (res.ok) {
          const chunkTime = (Date.now() - chunkStart) / 1000
          this.recordSpeed(chunk.size, chunkTime)
          return 'ok'
        }
        if (res.status === 404) {
          this.cb.onError('上传会话已过期，请重新上传')
          return 'fail'
        }
        if (res.status === 413) {
          this.cb.onError('分片过大，服务器拒绝')
          return 'fail'
        }
        if (attempt < MAX_RETRIES - 1) {
          this.cb.onStatus(`分片 ${chunkIndex} 上传失败(${res.status})，第${attempt + 1}次重试...`)
          await this.sleep(RETRY_DELAY_MS * (attempt + 1))
          continue
        }
        const errText = await res.text().catch(() => '')
        this.cb.onError(`分片 ${chunkIndex} 上传失败(${res.status}): ${errText}`)
        return 'fail'
      } catch (err: any) {
        if (signal.aborted) return 'abort'
        if (attempt < MAX_RETRIES - 1) {
          this.cb.onStatus(`分片 ${chunkIndex} 网络错误，第${attempt + 1}次重试...`)
          await this.sleep(RETRY_DELAY_MS * (attempt + 1))
          continue
        }
        return 'fail'
      }
    }
    return 'fail'
  }

  private recordSpeed(bytes: number, seconds: number) {
    const now = Date.now()
    this.speedSamples.push({ time: now, bytes })
    if (this.speedSamples.length > SPEED_WINDOW_SIZE * 2) {
      this.speedSamples = this.speedSamples.slice(-SPEED_WINDOW_SIZE)
    }
  }

  private calcInstantSpeed(): number {
    if (this.speedSamples.length < 2) return 0
    const recent = this.speedSamples.slice(-SPEED_WINDOW_SIZE)
    if (recent.length < 2) return 0
    const totalBytes = recent.reduce((sum, s) => sum + s.bytes, 0)
    const timeSpan = (recent[recent.length - 1].time - recent[0].time) / 1000
    if (timeSpan <= 0) return 0
    return totalBytes / timeSpan
  }

  private async uploadAllChunks(file: File, uploadId: string, signal: AbortSignal): Promise<boolean> {
    const queue: number[] = []
    for (let i = 0; i < this.totalChunks; i++) queue.push(i)
    return this.runChunkWorkers(file, uploadId, queue, signal)
  }

  private async uploadMissingChunks(file: File, uploadId: string, missingChunks: number[], signal: AbortSignal): Promise<boolean> {
    return this.runChunkWorkers(file, uploadId, missingChunks, signal)
  }

  private async runChunkWorkers(file: File, uploadId: string, chunkIndices: number[], signal: AbortSignal): Promise<boolean> {
    const queue = [...chunkIndices]
    let failed = false
    let localCompleted = 0
    const totalToUpload = chunkIndices.length

    const worker = async () => {
      while (queue.length > 0 && !failed && !signal.aborted) {
        const idx = queue.shift()
        if (idx === undefined) break

        const start = idx * CHUNK_SIZE
        const end = Math.min(start + CHUNK_SIZE, file.size)
        const chunk = file.slice(start, end)

        const result = await this.uploadChunk(uploadId, chunk, idx, signal)
        if (result === 'abort') return
        if (result === 'fail') {
          failed = true
          return
        }

        localCompleted++
        this.completedChunks++
        this.uploadedBytes = Math.min(this.completedChunks * CHUNK_SIZE, file.size)
        this.reportProgress()
        this.cb.onStatus(`正在上传分片 ${this.completedChunks}/${this.totalChunks}...`)
      }
    }

    const workerCount = Math.min(CONCURRENCY, queue.length)
    const workers: Promise<void>[] = []
    for (let i = 0; i < workerCount; i++) {
      workers.push(worker())
    }

    await Promise.all(workers)

    if (failed) {
      this.paused = true
      this.cb.onError('分片上传中断，请回到此页面自动续传')
      return false
    }

    if (this.completedChunks < this.totalChunks && signal.aborted) {
      this.paused = true
      return false
    }

    return true
  }

  private async completeUpload(uploadId: string, signal: AbortSignal): Promise<string | null> {
    try {
      const res = await fetch(`${API_BASE}/upload/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id: uploadId }),
        signal,
      })
      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        this.cb.onError(`合并文件失败(${res.status}): ${errText}`)
        return null
      }
      const data = await res.json()

      if (data.status === 'incomplete' && data.missing_chunks?.length > 0) {
        this.cb.onStatus(`补传 ${data.missing_chunks.length} 个缺失分片...`)
        if (!this.currentFile) {
          this.cb.onError('补传失败：文件引用丢失')
          return null
        }
        for (const idx of data.missing_chunks) {
          if (signal.aborted) return null
          const start = idx * CHUNK_SIZE
          const end = Math.min(start + CHUNK_SIZE, this.totalBytes)
          const chunk = this.currentFile.slice(start, end)
          const result = await this.uploadChunk(uploadId, chunk, idx, signal)
          if (result !== 'ok') {
            this.cb.onError('补传失败')
            return null
          }
        }
        const retryRes = await fetch(`${API_BASE}/upload/complete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ upload_id: uploadId }),
          signal,
        })
        if (!retryRes.ok) {
          this.cb.onError('合并文件失败')
          return null
        }
        return (await retryRes.json()).task_id || uploadId
      }

      return data.task_id || uploadId
    } catch (err: any) {
      if (signal.aborted) return null
      this.cb.onError('合并文件失败: ' + err.message)
      return null
    }
  }

  private reportProgress() {
    const now = Date.now()
    if (now - this.lastReportTime < 200) return
    this.lastReportTime = now

    const percent = Math.min(100, Math.round((this.uploadedBytes / this.totalBytes) * 100))
    this.cb.onProgress(percent, this.uploadedBytes, this.totalBytes)

    const speed = this.calcInstantSpeed()
    if (speed > 0 || this.speedSamples.length >= 2) {
      this.cb.onSpeed(speed)
      const bytesLeft = this.totalBytes - this.uploadedBytes
      this.cb.onEta(speed > 0 ? bytesLeft / speed : 0)
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms))
  }

  static getPendingUploads(): PendingUpload[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return []
      const all: PendingUpload[] = JSON.parse(raw)
      const now = Date.now()
      const valid = all.filter(p => now - p.createdAt < UPLOAD_TTL_MS)
      if (valid.length !== all.length) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(valid))
      }
      return valid
    } catch {
      return []
    }
  }

  private savePendingUpload(pending: PendingUpload) {
    const all = VideoUploader.getPendingUploads()
    const idx = all.findIndex(p => p.uploadId === pending.uploadId)
    if (idx >= 0) {
      all[idx] = pending
    } else {
      all.push(pending)
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all))
  }

  private removePendingUpload(uploadId: string) {
    const all = VideoUploader.getPendingUploads()
    const filtered = all.filter(p => p.uploadId !== uploadId)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered))
  }

  static removePendingUpload(uploadId: string) {
    const all = VideoUploader.getPendingUploads()
    const filtered = all.filter(p => p.uploadId !== uploadId)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered))
  }

  isPaused() {
    return this.paused
  }

  getCurrentUploadId() {
    return this.currentUploadId
  }
}
