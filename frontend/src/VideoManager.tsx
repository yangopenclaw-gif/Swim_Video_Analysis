// v2.1
import React, { useState, useEffect, useRef, useCallback } from 'react'


const API_BASE = '/api'

const PRESET_MARKERS = [
  { key: 'start_signal', label: '发令响', color: '#ea4335' },
  { key: 'dive_complete', label: '起发潜水完成', color: '#ff6d00' },
  { key: 'half_touch', label: '半程触壁', color: '#1a73e8' },
  { key: 'turn_emerge', label: '转身出水点', color: '#7c3aed' },
  { key: 'finish_touch', label: '全程触壁', color: '#34a853' },
] as const

type MarkerKey = typeof PRESET_MARKERS[number]['key']

interface VideoInfo {
  id: string
  file_name: string
  display_name?: string
  athlete_name?: string
  athlete_id?: string
  competition_name?: string
  competition_id?: string
  upload_time?: string
  file_size?: number
  duration?: number
  linked_record_id?: string
}

interface Marker {
  id: string
  time_seconds: number
  label: string
  color: string
  marker_key?: string
}

interface RecordOption {
  id: string
  swimmer_name: string
  race_name: string | null
  pool_length: number
  race_distance: number
}

interface UploadTask {
  id: string
  fileName: string
  progress: number
  speed: string
  loaded: number
  total: number
  status: 'uploading' | 'done' | 'error'
  eta: string
  videoId: string | null
  abortController: AbortController | null
}

const globalUploads: { tasks: UploadTask[]; listeners: Set<() => void> } = { tasks: [], listeners: new Set() }

function subscribeUploads(fn: () => void) { globalUploads.listeners.add(fn); return () => { globalUploads.listeners.delete(fn) } }
function notifyUploads() { globalUploads.listeners.forEach(fn => { try { fn() } catch {} }) }

export { globalUploads, subscribeUploads }

export const UploadStatusBar: React.FC = () => {
  const [, tick] = useState(0)
  useEffect(() => { const unsub = subscribeUploads(() => tick(n => n + 1)); return unsub }, [])
  const active = globalUploads.tasks.filter(t => t.status === 'uploading')
  if (active.length === 0) return null
  const cancelUpload = (task: UploadTask) => {
    if (task.abortController) task.abortController.abort()
    task.status = 'error'
    task.speed = '已取消'
    notifyUploads()
    setTimeout(() => { globalUploads.tasks = globalUploads.tasks.filter(t => t !== task); notifyUploads() }, 1500)
  }
  return (
    <div style={{ position: 'fixed', bottom: 0, left: 0, right: 0, background: 'var(--bg-card)', borderTop: '1px solid var(--border)', padding: '8px 16px', zIndex: 300, boxShadow: '0 -2px 8px rgba(0,0,0,0.1)' }}>
      {active.map(t => (
        <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.85rem' }}>
          <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.fileName}</span>
          <div style={{ width: 120, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden', flexShrink: 0 }}>
            <div style={{ height: '100%', width: `${t.progress}%`, background: 'var(--primary)', borderRadius: 3, transition: 'width 0.3s' }} />
          </div>
          <span style={{ width: 40, textAlign: 'right', flexShrink: 0 }}>{t.progress}%</span>
          <span style={{ width: 80, textAlign: 'right', color: 'var(--text-secondary)', flexShrink: 0 }}>{t.speed}</span>
          <span style={{ width: 60, textAlign: 'right', color: 'var(--text-secondary)', flexShrink: 0, fontSize: '0.8rem' }}>{t.eta}</span>
          <button onClick={() => cancelUpload(t)} style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: '0.85rem', padding: '0 4px', userSelect: 'none' }}>✕</button>
        </div>
      ))}
    </div>
  )
}

export const VideoManager: React.FC = () => {
  const [videos, setVideos] = useState<VideoInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [playingVideo, setPlayingVideo] = useState<VideoInfo | null>(null)
  const [editingVideo, setEditingVideo] = useState<VideoInfo | null>(null)
  const [records, setRecords] = useState<RecordOption[]>([])
  const [competitions, setCompetitions] = useState<{ id: string; name: string }[]>([])
  const [, uploadTick] = useState(0)
  const [pwModal, setPwModal] = useState<{ action: 'edit' | 'delete'; target: VideoInfo; password: string; error: string } | null>(null)
  useEffect(() => { const unsub = subscribeUploads(() => uploadTick(n => n + 1)); return unsub }, [])

  const fetchVideos = useCallback(async () => {
    setLoading(true)
    try { const res = await fetch(`${API_BASE}/videos/list`); if (res.ok) setVideos(await res.json()) } catch {} finally { setLoading(false) }
  }, [])

  const fetchRecords = useCallback(async () => {
    try { const res = await fetch(`${API_BASE}/all_records`); if (res.ok) setRecords((await res.json()).map((r: any) => ({ id: r.id, swimmer_name: r.swimmer_name, race_name: r.race_name, pool_length: r.pool_length, race_distance: r.race_distance }))) } catch {}
  }, [])

  const fetchCompetitions = useCallback(async () => {
    try { const res = await fetch(`${API_BASE}/competitions`); if (res.ok) setCompetitions(await res.json()) } catch {}
  }, [])

  useEffect(() => { fetchVideos(); fetchRecords(); fetchCompetitions() }, [fetchVideos, fetchRecords, fetchCompetitions])

  useEffect(() => {
    const handler = (e: any) => {
      const videoId = e.detail
      if (videoId && videos.length > 0) {
        const v = videos.find((x: VideoInfo) => x.id === videoId)
        if (v) setPlayingVideo(v)
      } else if (videoId) {
        fetch(`${API_BASE}/videos/list`).then(r => r.ok ? r.json() : []).then((list: VideoInfo[]) => {
          const v = list.find((x: VideoInfo) => x.id === videoId)
          if (v) { setVideos(list); setPlayingVideo(v) }
        }).catch(() => {})
      }
    }
    window.addEventListener('playVideo', handler)
    return () => { window.removeEventListener('playVideo', handler) }
  }, [videos])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const task: UploadTask = { id: Date.now().toString(), fileName: file.name, progress: 0, speed: '', loaded: 0, total: file.size, status: 'uploading', eta: '', videoId: null, abortController: new AbortController() }
    globalUploads.tasks.push(task)
    notifyUploads()

    const CHUNK = 512 * 1024
    const totalChunks = Math.ceil(file.size / CHUNK)
    const startTime = Date.now()
    let uploadMode: 'formdata' | 'base64' | 'raw' = 'formdata'

    const updateUI = () => {
      const elapsed = (Date.now() - startTime) / 1000
      if (elapsed > 0.5 && task.loaded > 0) {
        const bps = task.loaded / elapsed
        task.speed = bps > 1024 * 1024 ? `${(bps / 1024 / 1024).toFixed(1)} MB/s` : `${(bps / 1024).toFixed(0)} KB/s`
        const remaining = (file.size - task.loaded) / bps
        task.eta = remaining < 60 ? `约${Math.ceil(remaining)}秒` : `约${Math.floor(remaining / 60)}分${Math.ceil(remaining % 60)}秒`
      }
      notifyUploads()
    }

    const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

    const uploadChunkWithRetry = async (uploadId: string, chunkIndex: number, blob: Blob, retries = 3): Promise<boolean> => {
      for (let attempt = 0; attempt < retries; attempt++) {
        if (task.abortController?.signal.aborted) return false
        try {
          if (uploadMode === 'formdata') {
            const fd = new FormData()
            fd.append('chunk', blob, `chunk_${chunkIndex}`)
            const res = await fetch(`${API_BASE}/upload/chunk?upload_id=${encodeURIComponent(uploadId)}&chunk_index=${chunkIndex}`, {
              method: 'POST',
              body: fd,
              signal: task.abortController?.signal,
            })
            if (res.ok) return true
            if (res.status === 404) { task.speed = '会话过期'; return false }
            if (attempt === 0 && res.status >= 400) {
              uploadMode = 'base64'
              task.speed = `切换Base64模式...`
              updateUI()
              return uploadChunkWithRetry(uploadId, chunkIndex, blob, retries - attempt)
            }
          } else if (uploadMode === 'base64') {
            const arrayBuf = await blob.arrayBuffer()
            const uint8 = new Uint8Array(arrayBuf)
            let binary = ''
            for (let i = 0; i < uint8.length; i++) binary += String.fromCharCode(uint8[i])
            const b64 = btoa(binary)
            const res = await fetch(`${API_BASE}/upload/chunk?upload_id=${encodeURIComponent(uploadId)}&chunk_index=${chunkIndex}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ data: b64 }),
              signal: task.abortController?.signal,
            })
            if (res.ok) return true
            if (res.status === 404) { task.speed = '会话过期'; return false }
            if (attempt === 0 && res.status >= 400) {
              uploadMode = 'raw'
              task.speed = `切换原始模式...`
              updateUI()
              return uploadChunkWithRetry(uploadId, chunkIndex, blob, retries - attempt)
            }
          } else {
            const res = await fetch(`${API_BASE}/upload/chunk?upload_id=${encodeURIComponent(uploadId)}&chunk_index=${chunkIndex}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/octet-stream' },
              body: blob,
              signal: task.abortController?.signal,
            })
            if (res.ok) return true
            if (res.status === 404) { task.speed = '会话过期'; return false }
          }
          if (attempt < retries - 1) {
            task.speed = `分片${chunkIndex + 1}失败，重试${attempt + 1}/${retries}...`
            updateUI()
            await sleep(2000 * (attempt + 1))
          }
        } catch (err: any) {
          if (task.abortController?.signal.aborted) return false
          if (attempt === 0 && uploadMode === 'formdata') {
            uploadMode = 'base64'
            task.speed = `FormData失败，切换Base64...`
            updateUI()
            return uploadChunkWithRetry(uploadId, chunkIndex, blob, retries - attempt)
          }
          if (attempt < retries - 1) {
            task.speed = `分片${chunkIndex + 1}网络错误，重试${attempt + 1}/${retries}...`
            updateUI()
            await sleep(2000 * (attempt + 1))
          }
        }
      }
      return false
    }

    try {
      task.speed = '探测连接...'
      updateUI()
      try {
        const probeRes = await fetch(`${API_BASE}/upload/probe`, {
          method: 'POST',
          body: new ArrayBuffer(16),
          signal: task.abortController?.signal,
        })
        if (!probeRes.ok) { task.speed = '连接探测失败'; task.status = 'error'; updateUI(); return }
      } catch {
        task.speed = '无法连接服务器'; task.status = 'error'; updateUI(); return
      }

      task.speed = '初始化...'
      updateUI()
      const initRes = await fetch(`${API_BASE}/upload/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, file_size: file.size }),
        signal: task.abortController?.signal,
      })
      if (!initRes.ok) { task.speed = '初始化失败'; task.status = 'error'; updateUI(); return }
      const { upload_id } = await initRes.json()

      for (let i = 0; i < totalChunks; i++) {
        if (task.abortController?.signal.aborted) return
        const start = i * CHUNK
        const end = Math.min(start + CHUNK, file.size)
        const blob = file.slice(start, end)

        task.speed = `分片 ${i + 1}/${totalChunks} [${uploadMode}] (${(blob.size / 1024).toFixed(0)}KB)`
        updateUI()

        const ok = await uploadChunkWithRetry(upload_id, i, blob)
        if (!ok) {
          task.status = 'error'
          task.speed = `分片${i + 1}上传失败(模式:${uploadMode})`
          updateUI()
          return
        }

        task.loaded = end
        task.progress = Math.round((end / file.size) * 100)
        updateUI()
      }

      task.speed = '合并中...'
      task.progress = 99
      updateUI()

      const compRes = await fetch(`${API_BASE}/upload/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ upload_id }),
        signal: task.abortController?.signal,
      })
      if (!compRes.ok) { task.speed = '合并失败'; task.status = 'error'; updateUI(); return }
      const compData = await compRes.json()

      task.videoId = compData.video_id || upload_id
      task.progress = 100
      task.status = 'done'
      task.speed = '上传完成'
      task.eta = ''
      updateUI()
      fetchVideos()
    } catch (err: any) {
      if (task.abortController?.signal.aborted) {
        task.status = 'error'
        task.speed = '已取消'
      } else {
        task.status = 'error'
        task.speed = err.message || '上传失败'
      }
      updateUI()
    }
    setTimeout(() => { globalUploads.tasks = globalUploads.tasks.filter(t => t !== task); notifyUploads() }, 5000)
    e.target.value = ''
  }

  const handleDelete = (v: VideoInfo) => {
    setPwModal({ action: 'delete', target: v, password: '', error: '' })
  }

  const handleSaveEdit = async (data: Partial<VideoInfo>) => {
    if (!editingVideo) return
    try { await fetch(`${API_BASE}/videos/${editingVideo.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...data, password: 'ycz' }) }); setEditingVideo(null); fetchVideos() } catch {}
  }

  const confirmPwAction = async () => {
    if (!pwModal) return
    if (pwModal.password !== 'ycz') { setPwModal({ ...pwModal, error: '密码错误' }); return }
    if (pwModal.action === 'delete') {
      try {
        const res = await fetch(`${API_BASE}/videos/${pwModal.target.id}/delete`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pwModal.password }) })
        if (res.ok) { setPwModal(null); fetchVideos() }
        else { const d = await res.json().catch(() => ({})); setPwModal({ ...pwModal, error: d.detail || '删除失败' }) }
      } catch { setPwModal({ ...pwModal, error: '网络错误' }) }
    } else if (pwModal.action === 'edit') {
      setEditingVideo(pwModal.target); setPwModal(null)
    }
  }

  const cancelUpload = (task: UploadTask) => {
    if (task.abortController) task.abortController.abort()
    task.status = 'error'
    task.speed = '已取消'
    notifyUploads()
    setTimeout(() => { globalUploads.tasks = globalUploads.tasks.filter(t => t !== task); notifyUploads() }, 1500)
  }

  if (playingVideo) return <VideoPlayerView video={playingVideo} records={records} onBack={() => setPlayingVideo(null)} onEdit={() => { setPlayingVideo(null); setPwModal({ action: 'edit', target: playingVideo, password: '', error: '' }) }} />
  if (editingVideo) return <VideoEditForm video={editingVideo} records={records} competitions={competitions} onSave={handleSaveEdit} onCancel={() => setEditingVideo(null)} />

  const activeUploads = globalUploads.tasks.filter(t => t.status === 'uploading')

  return (
    <div>
      {activeUploads.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-title"><span className="icon">📤</span> 上传中</div>
          {activeUploads.map((t, i) => (
            <div key={i} style={{ marginBottom: i < activeUploads.length - 1 ? 10 : 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: '0.85rem' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: 8 }}>{t.fileName}</span>
                <span style={{ fontWeight: 600, color: 'var(--primary)', flexShrink: 0, marginRight: 8 }}>{t.progress}%</span>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginRight: 8 }}>{t.speed}</span>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginRight: 8 }}>{t.eta}</span>
                <button onClick={() => cancelUpload(t)} className="btn btn-sm btn-danger" style={{ padding: '2px 8px', fontSize: '0.8rem' }}>取消</button>
              </div>
              <div style={{ width: '100%', height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${t.progress}%`, background: 'var(--primary)', borderRadius: 4, transition: 'width 0.3s' }} />
              </div>
            </div>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>视频管理</h2>
        <label className="btn btn-primary" style={{ cursor: 'pointer' }}>
          上传视频
          <input type="file" accept="video/*" onChange={handleUpload} style={{ display: 'none' }} />
        </label>
      </div>
      {loading ? <div className="loading"><div className="spinner" /><p>加载中...</p></div>
        : videos.length === 0 ? <div className="card"><div className="empty-state"><div className="icon">🎥</div><p>暂无视频</p></div></div>
        : <div className="video-grid">{videos.map(v => (
          <div key={v.id} className="video-card">
            <div className="video-card-thumb" onClick={() => setPlayingVideo(v)}><span className="video-card-play">▶</span></div>
            <div className="video-card-info">
              <div className="video-card-name" onClick={() => setPlayingVideo(v)}>{v.display_name || v.file_name}</div>
              {v.athlete_name && <div className="video-card-meta">运动员：{v.athlete_name}</div>}
              {v.competition_name && <div className="video-card-meta">比赛：{v.competition_name}</div>}
            </div>
            <div className="video-card-actions">
              <button className="btn btn-sm btn-outline" onClick={() => setPwModal({ action: 'edit', target: v, password: '', error: '' })}>编辑</button>
              <button className="btn btn-sm btn-danger" onClick={() => handleDelete(v)}>删除</button>
            </div>
          </div>
        ))}</div>}
      {pwModal && (
        <div className="modal-overlay" onClick={() => setPwModal(null)} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius)', padding: 24, maxWidth: 400, width: '90%' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 12 }}>{pwModal.action === 'delete' ? '确认删除视频' : '确认编辑视频'}</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 12 }}>请输入密码确认操作</p>
            <div className="form-group" style={{ marginBottom: 12 }}>
              <label>密码 *</label>
              <input type="password" value={pwModal.password} onChange={e => setPwModal({ ...pwModal, password: e.target.value, error: '' })} placeholder="请输入密码" style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }} />
            </div>
            {pwModal.error && <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fdecea', borderRadius: 6, fontSize: '0.85rem', color: '#b71c1c' }}>{pwModal.error}</div>}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={() => setPwModal(null)}>取消</button>
              <button className={pwModal.action === 'delete' ? 'btn btn-danger' : 'btn btn-primary'} onClick={confirmPwAction}>{pwModal.action === 'delete' ? '确认删除' : '确认编辑'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}



const VideoPlayerView: React.FC<{ video: VideoInfo; records: RecordOption[]; onBack: () => void; onEdit: () => void }> = ({ video, records, onBack, onEdit }) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const videoContainerRef = useRef<HTMLDivElement>(null)
  const [markers, setMarkers] = useState<Marker[]>([])
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [dragTime, setDragTime] = useState(0)
  const [fps, setFps] = useState(30)
  const [isPlaying, setIsPlaying] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [calcResult, setCalcResult] = useState<any>(null)
  const [calcLoading, setCalcLoading] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [saving, setSaving] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [linkRecordId, setLinkRecordId] = useState('')
  const [linkMsg, setLinkMsg] = useState('')
  const [bufferedPct, setBufferedPct] = useState(0)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [submitForm, setSubmitForm] = useState<any>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitMsg, setSubmitMsg] = useState('')
  const [hoverPct, setHoverPct] = useState<number | null>(null)
  const [hoverTime, setHoverTime] = useState(0)
  const [videoError, setVideoError] = useState(false)
  const progressRef = useRef<HTMLDivElement>(null)

  useEffect(() => { fetch(`${API_BASE}/videos/${video.id}/markers`).then(r => r.ok ? r.json() : []).then(setMarkers).catch(() => {}) }, [video.id])

  const handleTimeUpdate = () => {
    if (!isDragging && videoRef.current) {
      setCurrentTime(videoRef.current.currentTime)
    }
  }
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration)
    }
  }
  const handleProgress = () => {
    if (!videoRef.current || !duration) return
    const buf = videoRef.current.buffered
    if (buf.length > 0) setBufferedPct((buf.end(buf.length - 1) / duration) * 100)
  }
  const togglePlay = () => { if (!videoRef.current) return; videoRef.current.paused ? (videoRef.current.play(), setIsPlaying(true)) : (videoRef.current.pause(), setIsPlaying(false)) }

  const toggleFullscreen = () => {
    if (!videoContainerRef.current) return
    if (!document.fullscreenElement) {
      videoContainerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {})
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {})
    }
  }

  useEffect(() => {
    const h = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', h)
    return () => document.removeEventListener('fullscreenchange', h)
  }, [])

  const seekTo = useCallback((time: number) => {
    if (videoRef.current) {
      const t = Math.max(0, Math.min(time, duration || Infinity))
      videoRef.current.currentTime = t
      setCurrentTime(t)
    }
  }, [duration])

  const stepFrame = useCallback((dir: number) => {
    if (!videoRef.current) return
    videoRef.current.pause()
    setIsPlaying(false)
    const target = videoRef.current.currentTime + dir / fps
    videoRef.current.currentTime = Math.max(0, Math.min(target, duration || Infinity))
  }, [fps, duration])

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return
      if (e.key === 'ArrowLeft') { e.preventDefault(); stepFrame(-1) }
      else if (e.key === 'ArrowRight') { e.preventDefault(); stepFrame(1) }
      else if (e.key === ' ') { e.preventDefault(); togglePlay() }
      else if (e.key === 'f' || e.key === 'F') { e.preventDefault(); toggleFullscreen() }
    }
    window.addEventListener('keydown', h); return () => window.removeEventListener('keydown', h)
  }, [stepFrame])

  const calcTimeFromX = (clientX: number) => {
    if (!progressRef.current || !duration) return 0
    const r = progressRef.current.getBoundingClientRect()
    return Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * duration
  }

  const handleProgressMouseDown = (e: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>) => {
    setIsDragging(true)
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX
    setDragTime(calcTimeFromX(clientX))
    const onMove = (ev: MouseEvent | TouchEvent) => {
      const cx = 'touches' in ev ? ev.touches[0].clientX : ev.clientX
      setDragTime(calcTimeFromX(cx))
    }
    const onUp = (ev: MouseEvent | TouchEvent) => {
      setIsDragging(false)
      const cx = 'changedTouches' in ev ? ev.changedTouches[0].clientX : ev.clientX
      seekTo(calcTimeFromX(cx))
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.removeEventListener('touchmove', onMove)
      document.removeEventListener('touchend', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    document.addEventListener('touchmove', onMove, { passive: false })
    document.addEventListener('touchend', onUp)
  }

  const handleProgressHover = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!duration) return
    const r = progressRef.current!.getBoundingClientRect()
    const p = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width))
    setHoverPct(p * 100)
    setHoverTime(p * duration)
  }

  const addPresetMarker = async (preset: typeof PRESET_MARKERS[number]) => {
    setErrorMsg('')
    const existing = markers.find(m => m.marker_key === preset.key)
    if (existing) { try { const r = await fetch(`${API_BASE}/videos/${video.id}/markers/${existing.id}`, { method: 'DELETE' }); if (!r.ok) { setErrorMsg('删除旧标注失败'); return } } catch { setErrorMsg('网络错误'); return } }
    try {
      const res = await fetch(`${API_BASE}/videos/${video.id}/markers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ time_seconds: currentTime, label: preset.label, color: preset.color, marker_key: preset.key }) })
      if (res.ok) { const m = await res.json(); setMarkers(prev => [...prev.filter(x => x.marker_key !== preset.key), m].sort((a, b) => a.time_seconds - b.time_seconds)) }
      else { const err = await res.json().catch(() => ({})); setErrorMsg(`标注失败: ${err.detail || '未知错误'}`) }
    } catch { setErrorMsg('网络错误') }
  }

  const deleteMarker = async (id: string) => { try { await fetch(`${API_BASE}/videos/${video.id}/markers/${id}`, { method: 'DELETE' }); setMarkers(prev => prev.filter(m => m.id !== id)) } catch {} }

  const autoDetectStartSignal = async () => {
    setDetecting(true); setErrorMsg('')
    try {
      const res = await fetch(`${API_BASE}/videos/${video.id}/detect_start_signal`, { method: 'POST' })
      if (res.ok) { const data = await res.json(); seekTo(data.onset_time); await addPresetMarker(PRESET_MARKERS.find(p => p.key === 'start_signal')!) }
      else { const err = await res.json().catch(() => ({})); setErrorMsg(`检测失败: ${err.detail || '未知错误'}`) }
    } catch (e: any) { setErrorMsg(`检测失败: ${e.message}`) }
    setDetecting(false)
  }

  const handleCalculate = async () => {
    setCalcLoading(true); setCalcResult(null)
    try { const mm: Record<string, number> = {}; markers.forEach(m => { if (m.marker_key) mm[m.marker_key] = m.time_seconds }); const res = await fetch(`${API_BASE}/videos/${video.id}/calculate_from_markers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ markers: mm }) }); if (res.ok) setCalcResult(await res.json()) } catch {}
    setCalcLoading(false)
  }

  const handleSaveResult = async () => {
    if (!calcResult) return; setSaving(true); setSaveMsg('')
    try { const mm: Record<string, number> = {}; markers.forEach(m => { if (m.marker_key) mm[m.marker_key] = m.time_seconds }); const res = await fetch(`${API_BASE}/videos/${video.id}/save_marker_result`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ metrics: calcResult.metrics, markers: mm, swimmer_name: video.athlete_name || '' }) }); if (res.ok) setSaveMsg('保存成功'); else setSaveMsg('保存失败') } catch { setSaveMsg('保存失败') }
    setSaving(false)
  }

  const handleLinkToRecord = async () => {
    if (!linkRecordId || !calcResult) return; setSaving(true); setLinkMsg('')
    try { const res = await fetch(`${API_BASE}/videos/${video.id}/link_to_record`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ record_id: linkRecordId, metrics: calcResult.metrics }) }); if (res.ok) setLinkMsg('已关联并覆盖指标'); else setLinkMsg('关联失败') } catch { setLinkMsg('关联失败') }
    setSaving(false)
  }

  const buildHalfMetrics = (metrics: Record<string, any>, raceDistance: number) => {
    const result = { ...metrics }
    const numHalves = Math.max(1, raceDistance / 50)
    const qianCheng = result['前程用时']
    const houCheng = result['后程用时']
    if (qianCheng != null) result['第1半程用时'] = qianCheng
    if (numHalves >= 2 && houCheng != null) result['第2半程用时'] = houCheng
    for (let i = 3; i <= numHalves; i++) {
      if (result[`第${i}半程用时`] == null) result[`第${i}半程用时`] = 0
    }
    return result
  }

  const openSubmitForm = async () => {
    if (!calcResult) return
    const comps = await fetch(`${API_BASE}/competitions`).then(r => r.ok ? r.json() : []).catch(() => [])
    let existingRecordId: string | null = null
    try {
      const checkRes = await fetch(`${API_BASE}/videos/${video.id}/linked_record`)
      if (checkRes.ok) { const d = await checkRes.json(); if (d.record_id) existingRecordId = d.record_id }
    } catch {}
    const initMetrics = buildHalfMetrics({ ...calcResult.metrics }, 100)
    setSubmitForm({
      swimmer_name: video.athlete_name || '',
      stroke_type: '自由泳',
      pool_length: 50,
      race_distance: 100,
      competition_id: '',
      race_year: new Date().getFullYear().toString(),
      race_month: (new Date().getMonth() + 1).toString().padStart(2, '0'),
      metrics: initMetrics,
      competitions: comps,
      new_comp: { name: '', date: '', location: '' },
      existing_record_id: existingRecordId,
      password: '',
    })
    setSubmitMsg('')
  }

  const handleConfirmSubmit = async () => {
    if (!submitForm) return
    if (submitForm.existing_record_id && submitForm.password !== 'ycz') {
      setSubmitMsg('该视频已有提交记录，需输入密码才能覆盖')
      return
    }
    setSubmitting(true); setSubmitMsg('')
    const finalMetrics = buildHalfMetrics(submitForm.metrics, submitForm.race_distance)
    try {
      let compId = submitForm.competition_id
      if (compId === '__new__') compId = ''
      if (!compId && submitForm.new_comp.name) {
        const compRes = await fetch(`${API_BASE}/competitions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: submitForm.new_comp.name, date: submitForm.new_comp.date || `${submitForm.race_year}-${submitForm.race_month}`, location: submitForm.new_comp.location }) })
        if (compRes.ok) compId = (await compRes.json()).id
      }
      if (submitForm.existing_record_id) {
        const res = await fetch(`${API_BASE}/records/${submitForm.existing_record_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            password: 'ycz',
            swimmer_name: submitForm.swimmer_name,
            pool_length: submitForm.pool_length,
            race_distance: submitForm.race_distance,
            stroke_type: submitForm.stroke_type,
            competition_id: compId || null,
            race_date: `${submitForm.race_year}-${submitForm.race_month}`,
            metrics: finalMetrics,
          }),
        })
        if (res.ok) {
          setSubmitMsg('覆盖成功！')
          setTimeout(() => { setSubmitForm(null) }, 1500)
        } else {
          const err = await res.json().catch(() => ({}))
          setSubmitMsg(`覆盖失败: ${err.detail || '未知错误'}`)
        }
      } else {
        const res = await fetch(`${API_BASE}/manual_record`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            swimmer_name: submitForm.swimmer_name,
            pool_length: submitForm.pool_length,
            race_distance: submitForm.race_distance,
            stroke_type: submitForm.stroke_type,
            competition_id: compId || null,
            race_date: `${submitForm.race_year}-${submitForm.race_month}`,
            metrics: finalMetrics,
            linked_video_id: video.id,
          }),
        })
        if (res.ok) {
          setSubmitMsg('提交成功！')
          setTimeout(() => { setSubmitForm(null) }, 1500)
        } else {
          const err = await res.json().catch(() => ({}))
          setSubmitMsg(`提交失败: ${err.detail || '未知错误'}`)
        }
      }
    } catch { setSubmitMsg('网络错误') }
    setSubmitting(false)
  }

  const fmt = (s: number) => { const m = Math.floor(s / 60), sec = Math.floor(s % 60), ms = Math.floor((s % 1) * 100); return `${m}:${sec.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}` }
  const displayTime = isDragging ? dragTime : currentTime
  const pct = duration > 0 ? (displayTime / duration) * 100 : 0
  const getMk = (k: MarkerKey) => markers.find(m => m.marker_key === k)

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <button className="btn btn-outline" onClick={onBack}>← 返回</button>
        <h2 style={{ fontSize: '1rem', fontWeight: 600 }}>{video.display_name || video.file_name}</h2>
        <button className="btn btn-sm btn-outline" onClick={onEdit}>编辑</button>
      </div>

      <div ref={videoContainerRef} style={{ background: '#000', borderRadius: 12, overflow: 'hidden', position: 'relative' }}>
        <video
          ref={videoRef}
          src={`${API_BASE}/videos/${video.id}/stream`}
          playsInline
          preload="metadata"
          style={{ width: '100%', display: 'block', background: '#000', cursor: videoError ? 'default' : 'pointer', objectFit: 'contain', minHeight: 200 }}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onProgress={handleProgress}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onClick={() => { if (!videoError) togglePlay() }}
          onError={() => setVideoError(true)}
        />
        {videoError && (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.7)', color: '#fff', gap: 12 }}>
            <div style={{ fontSize: '3rem' }}>🎥</div>
            <div style={{ fontSize: '1rem', fontWeight: 600 }}>视频文件不存在或格式不支持</div>
            <div style={{ fontSize: '0.85rem', color: '#aaa' }}>请重新上传视频文件</div>
          </div>
        )}
        {!videoError && !isPlaying && duration === 0 && (
          <div onClick={togglePlay} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', background: 'rgba(0,0,0,0.3)' }}>
            <div style={{ width: 64, height: 64, background: 'rgba(255,255,255,0.9)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 12px rgba(0,0,0,0.3)' }}>
              <div style={{ width: 0, height: 0, borderTop: '14px solid transparent', borderBottom: '14px solid transparent', borderLeft: '22px solid #4F95FF', marginLeft: 4 }} />
            </div>
          </div>
        )}
        <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>
          <button onClick={toggleFullscreen} style={{ background: 'rgba(0,0,0,0.6)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 10px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, backdropFilter: 'blur(4px)' }}>
            {isFullscreen ? '✕ 退出全屏' : '⛶ 全屏'}
          </button>
        </div>
        <div style={{ padding: '12px 16px', background: '#1a1a1a' }}>
          <div
            ref={progressRef}
            onMouseDown={handleProgressMouseDown}
            onTouchStart={handleProgressMouseDown}
            onMouseMove={handleProgressHover}
            onMouseLeave={() => setHoverPct(null)}
            style={{ position: 'relative', height: 24, background: '#555', borderRadius: 12, cursor: 'pointer', marginBottom: 4, touchAction: 'none' }}
          >
            <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: `${bufferedPct}%`, background: '#888', borderRadius: 12, pointerEvents: 'none', transition: 'width 0.3s' }} />
            <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, #4F95FF, #60A5FA)', borderRadius: 12, pointerEvents: 'none', transition: isDragging ? 'none' : 'width 0.1s' }} />
            {markers.map(m => {
              const l = duration > 0 ? (m.time_seconds / duration) * 100 : 0
              return <div key={m.id} style={{ position: 'absolute', top: -4, left: `${l}%`, transform: 'translateX(-50%)', pointerEvents: 'none', zIndex: 2 }}><div style={{ width: 0, height: 0, borderLeft: '4px solid transparent', borderRight: '4px solid transparent', borderBottom: `5px solid ${m.color}` }} /><div style={{ width: 2, height: 24, background: m.color, margin: '0 auto' }} /></div>
            })}
            <div style={{ position: 'absolute', top: '50%', left: `${pct}%`, width: 18, height: 18, background: '#fff', borderRadius: '50%', transform: 'translate(-50%, -50%)', zIndex: 4, boxShadow: '0 1px 6px rgba(0,0,0,0.5)', border: '3px solid #4F95FF', cursor: 'grab' }} />
            {(hoverPct !== null || isDragging) && (
              <div style={{
                position: 'absolute',
                bottom: '100%',
                left: `${isDragging ? pct : hoverPct ?? 0}%`,
                transform: 'translateX(-50%)',
                marginBottom: 8,
                background: 'rgba(0,0,0,0.9)',
                color: '#fff',
                padding: '4px 10px',
                borderRadius: 4,
                fontSize: '0.8rem',
                fontFamily: 'monospace',
                whiteSpace: 'nowrap',
                pointerEvents: 'none',
                zIndex: 10,
              }}>
                {fmt(isDragging ? dragTime : hoverTime)}
                <div style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)', width: 0, height: 0, borderLeft: '4px solid transparent', borderRight: '4px solid transparent', borderTop: '4px solid rgba(0,0,0,0.9)' }} />
              </div>
            )}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, fontFamily: 'monospace', color: '#fff' }}>{fmt(displayTime)}</span>
            <span style={{ fontSize: '0.75rem', color: '#999' }}>帧 {Math.round(displayTime * fps)}/{Math.round(duration * fps)} ({fps}fps)</span>
            <span style={{ fontSize: '0.85rem', color: '#999', fontFamily: 'monospace' }}>{fmt(duration)}</span>
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', userSelect: 'none' }}>
            <button onClick={() => stepFrame(-10)} style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: '0.85rem' }}>⏪</button>
            <button onClick={() => stepFrame(-1)} style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: '0.85rem' }}>◀</button>
            <button onClick={togglePlay} style={{ background: '#4F95FF', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 16px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 }}>{isPlaying ? '⏸ 暂停' : '▶ 播放'}</button>
            <button onClick={() => stepFrame(1)} style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: '0.85rem' }}>▶</button>
            <button onClick={() => stepFrame(10)} style={{ background: 'rgba(255,255,255,0.15)', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: '0.85rem' }}>⏩</button>
            <select value={fps} onChange={e => setFps(Number(e.target.value))} style={{ marginLeft: 8, padding: '4px 8px', fontSize: '0.8rem', border: '1px solid #555', borderRadius: 4, background: '#333', color: '#fff' }}>
              {[24, 25, 30, 50, 60].map(f => <option key={f} value={f}>{f}fps</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title"><span className="icon">📌</span> 比赛标注 <button className="btn btn-sm btn-outline" onClick={autoDetectStartSignal} disabled={detecting} style={{ marginLeft: 8 }}>{detecting ? '检测中...' : '🔊 自动检测发令响'}</button></div>
        {errorMsg && <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fdecea', borderRadius: 6, fontSize: '0.85rem', color: '#b71c1c' }}>{errorMsg}</div>}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
          {PRESET_MARKERS.map(p => {
            const ex = getMk(p.key)
            return (
              <div key={p.key} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: ex ? `${p.color}11` : 'var(--bg)', borderRadius: 6, border: ex ? `1px solid ${p.color}44` : '1px solid var(--border)' }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: p.color, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 500 }}>{p.label}</div>
                  {ex && <div style={{ fontSize: '0.75rem', color: p.color, fontFamily: 'monospace' }}>{fmt(ex.time_seconds)}</div>}
                </div>
                {ex && <button style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer', fontSize: '0.75rem', padding: '2px 4px', userSelect: 'none' }} onClick={() => deleteMarker(ex.id)}>✕</button>}
                <button style={{ background: p.color, color: 'white', border: 'none', fontSize: '0.75rem', padding: '4px 10px', borderRadius: 4, cursor: 'pointer', userSelect: 'none', fontWeight: 500 }} onClick={() => addPresetMarker(p)}>{ex ? '更新' : '标注'}</button>
              </div>
            )
          })}
        </div>
      </div>

      <div className="card">
        <div className="card-title"><span className="icon">📊</span> 计算指标</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <button className="btn btn-primary" onClick={handleCalculate} disabled={calcLoading || markers.length === 0}>{calcLoading ? '计算中...' : '计算指标'}</button>
        </div>
        {calcResult && (
          <div>
            <table className="result-table"><thead><tr><th>指标</th><th>数值</th></tr></thead><tbody>
              {Object.entries(calcResult.metrics || {}).map(([k, v]: [string, any]) => <tr key={k}><td>{k}</td><td className="value">{typeof v === 'number' ? v.toFixed(3) + ' s' : String(v)}</td></tr>)}
            </tbody></table>
            {calcResult.warnings?.length > 0 && <div style={{ marginTop: 10, padding: '8px 12px', background: '#fff3e0', borderRadius: 6, fontSize: '0.8rem', color: '#e65100' }}>{calcResult.warnings.map((w: string, i: number) => <div key={i}>⚠️ {w}</div>)}</div>}
            <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="btn btn-success" onClick={handleSaveResult} disabled={saving}>{saving ? '保存中...' : '💾 保存结果'}</button>
              <button className="btn btn-primary" onClick={openSubmitForm} disabled={!calcResult.metrics || Object.keys(calcResult.metrics).length === 0}>📋 提交比赛记录</button>
              {saveMsg && <span style={{ fontSize: '0.85rem', color: saveMsg.includes('成功') ? 'var(--success)' : 'var(--danger)' }}>{saveMsg}</span>}
            </div>
            <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 8 }}>关联到已有记录（覆盖指标）</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <select value={linkRecordId} onChange={e => setLinkRecordId(e.target.value)} style={{ padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem', minWidth: 200 }}>
                  <option value="">选择记录...</option>
                  {records.map(r => <option key={r.id} value={r.id}>{r.swimmer_name} - {r.race_name || '未命名'} ({r.pool_length}m/{r.race_distance}m)</option>)}
                </select>
                <button className="btn btn-primary" onClick={handleLinkToRecord} disabled={!linkRecordId || saving}>{saving ? '关联中...' : '关联并覆盖'}</button>
                {linkMsg && <span style={{ fontSize: '0.85rem', color: linkMsg.includes('已关联') ? 'var(--success)' : 'var(--danger)' }}>{linkMsg}</span>}
              </div>
            </div>
          </div>
        )}
      </div>

      {submitForm && (
        <div onClick={() => { if (!submitting) setSubmitForm(null) }} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 20, maxWidth: 480, width: '92%', maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>📋 {submitForm.existing_record_id ? '覆盖比赛记录' : '提交比赛记录'}</h2>
              <button onClick={() => { if (!submitting) setSubmitForm(null) }} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--text-secondary)' }}>✕</button>
            </div>

            {submitForm.existing_record_id && (
              <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fff3e0', borderRadius: 6, fontSize: '0.8rem', color: '#e65100' }}>
                ⚠️ 该视频已有提交的记录，覆盖需输入密码
              </div>
            )}

            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>运动员姓名 *</label>
              <input type="text" value={submitForm.swimmer_name} onChange={e => setSubmitForm({ ...submitForm, swimmer_name: e.target.value })} style={{ width: '100%', padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }} placeholder="输入运动员姓名" />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 }}>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>泳姿</label>
                <select value={submitForm.stroke_type} onChange={e => setSubmitForm({ ...submitForm, stroke_type: e.target.value })} style={{ width: '100%', padding: '7px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }}>
                  {['自由泳', '蛙泳', '仰泳', '蝶泳'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>距离</label>
                <select value={submitForm.race_distance} onChange={e => { const d = parseInt(e.target.value); setSubmitForm({ ...submitForm, race_distance: d, metrics: buildHalfMetrics(submitForm.metrics, d) }) }} style={{ width: '100%', padding: '7px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }}>
                  {[50, 100, 200, 400].map(d => <option key={d} value={d}>{d}米</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>泳池</label>
                <select value={submitForm.pool_length} onChange={e => setSubmitForm({ ...submitForm, pool_length: parseInt(e.target.value) })} style={{ width: '100%', padding: '7px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }}>
                  <option value={50}>50米</option><option value={25}>25米</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 10 }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>比赛</label>
              <select value={submitForm.competition_id} onChange={e => { setSubmitForm({ ...submitForm, competition_id: e.target.value }); const c = submitForm.competitions?.find((x: any) => x.id === e.target.value); if (c?.date) { const p = c.date.split('-'); setSubmitForm((prev: any) => ({ ...prev, race_year: p[0] || prev.race_year, race_month: p[1]?.padStart(2, '0') || prev.race_month })) } }} style={{ width: '100%', padding: '7px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }}>
                <option value="">选择比赛...</option>
                {(submitForm.competitions || []).map((c: any) => <option key={c.id} value={c.id}>{c.name}{c.date ? ` (${c.date})` : ''}</option>)}
                <option value="__new__">+ 新建比赛...</option>
              </select>
            </div>

            {submitForm.competition_id === '__new__' && (
              <div style={{ marginBottom: 10, padding: '8px 10px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div><input value={submitForm.new_comp.name} onChange={e => setSubmitForm({ ...submitForm, new_comp: { ...submitForm.new_comp, name: e.target.value } })} style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }} placeholder="比赛名称" /></div>
                  <div><input type="date" value={submitForm.new_comp.date} onChange={e => setSubmitForm({ ...submitForm, new_comp: { ...submitForm.new_comp, date: e.target.value } })} style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }} /></div>
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>年份</label>
                <select value={submitForm.race_year} onChange={e => setSubmitForm({ ...submitForm, race_year: e.target.value })} style={{ width: '100%', padding: '7px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }}>
                  {Array.from({ length: 10 }, (_, i) => (new Date().getFullYear() - i).toString()).map(y => <option key={y} value={y}>{y}年</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>月份</label>
                <select value={submitForm.race_month} onChange={e => setSubmitForm({ ...submitForm, race_month: e.target.value })} style={{ width: '100%', padding: '7px 8px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }}>
                  {Array.from({ length: 12 }, (_, i) => (i + 1).toString().padStart(2, '0')).map(m => <option key={m} value={m}>{parseInt(m)}月</option>)}
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 10, padding: '8px 10px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 6, color: 'var(--primary)' }}>指标（可修改）</div>
              {Object.entries(submitForm.metrics || {}).map(([k, v]: [string, any]) => (
                <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{ flex: 1, fontSize: '0.8rem' }}>{k}</span>
                  <input type="number" step="0.001" value={v ?? ''} onChange={e => setSubmitForm({ ...submitForm, metrics: { ...submitForm.metrics, [k]: parseFloat(e.target.value) || 0 } })} style={{ width: 90, padding: '5px 6px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.8rem', textAlign: 'right' }} />
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', width: 16 }}>s</span>
                </div>
              ))}
            </div>

            {submitForm.existing_record_id && (
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 3, display: 'block' }}>密码 *</label>
                <input type="password" value={submitForm.password} onChange={e => setSubmitForm({ ...submitForm, password: e.target.value })} style={{ width: '100%', padding: '7px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }} placeholder="输入密码以覆盖已有记录" />
              </div>
            )}

            {submitMsg && <div style={{ marginBottom: 8, padding: '8px 12px', background: submitMsg.includes('成功') ? '#e8f5e9' : '#fdecea', borderRadius: 6, fontSize: '0.85rem', color: submitMsg.includes('成功') ? '#2e7d32' : '#b71c1c' }}>{submitMsg}</div>}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={() => setSubmitForm(null)} disabled={submitting}>取消</button>
              <button className="btn btn-primary" onClick={handleConfirmSubmit} disabled={submitting || !submitForm.swimmer_name || (submitForm.existing_record_id && submitForm.password !== 'ycz')}>{submitting ? '提交中...' : submitForm.existing_record_id ? '✓ 确认覆盖' : '✓ 确认提交'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


const VideoEditForm: React.FC<{ video: VideoInfo; records: RecordOption[]; competitions: { id: string; name: string }[]; onSave: (data: Partial<VideoInfo>) => void; onCancel: () => void }> = ({ video, records, competitions, onSave, onCancel }) => {
  const [form, setForm] = useState({ display_name: video.display_name || '', athlete_name: video.athlete_name || '', competition_id: video.competition_id || '', competition_name: video.competition_name || '', linked_record_id: video.linked_record_id || '' })
  const selectedComp = competitions.find(c => c.id === form.competition_id)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>编辑视频信息</h2>
        <button className="btn btn-outline" onClick={onCancel}>取消</button>
      </div>
      <div className="card">
        <div className="form-group" style={{ marginBottom: 12 }}><label>显示名称</label><input type="text" value={form.display_name} onChange={e => setForm(p => ({ ...p, display_name: e.target.value }))} placeholder={video.file_name} /></div>
        <div className="form-group" style={{ marginBottom: 12 }}><label>运动员姓名</label><input type="text" value={form.athlete_name} onChange={e => setForm(p => ({ ...p, athlete_name: e.target.value }))} placeholder="输入运动员姓名" /></div>
        <div className="form-group" style={{ marginBottom: 12 }}>
          <label>比赛</label>
          <select value={form.competition_id} onChange={e => { const c = competitions.find(x => x.id === e.target.value); setForm(p => ({ ...p, competition_id: e.target.value, competition_name: c ? c.name : '' })) }}>
            <option value="">选择比赛...</option>
            {competitions.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="form-group" style={{ marginBottom: 16 }}><label>关联分析记录</label><select value={form.linked_record_id} onChange={e => setForm(p => ({ ...p, linked_record_id: e.target.value }))}><option value="">不关联</option>{records.map(r => <option key={r.id} value={r.id}>{r.swimmer_name} - {r.race_name || '未命名'}</option>)}</select></div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}><button className="btn btn-outline" onClick={onCancel}>取消</button><button className="btn btn-primary" onClick={() => onSave(form)}>保存</button></div>
      </div>
    </div>
  )
}
