import React, { useEffect, useRef, useState, useCallback } from 'react'
import { VideoAnnotationOverlay } from './VideoAnnotationOverlay'
import { TimelineMarker } from './TimelineMarker'

const API_BASE = '/api'

const MARKER_TYPES = [
  { key: 'start_signal', label: '出发信号', color: '#ef4444' },
  { key: 'dive_start', label: '起跳', color: '#f97316' },
  { key: 'dive_enter', label: '入水', color: '#eab308' },
  { key: 'turn_touch', label: '转身触壁', color: '#3b82f6' },
  { key: 'turn_surface', label: '转身出水', color: '#06b6d4' },
  { key: 'finish_touch', label: '终点触壁', color: '#22c55e' },
] as const

type MarkerTypeKey = typeof MARKER_TYPES[number]['key']

const METRIC_LABELS: Record<string, string> = {
  reaction_time: '反应时间',
  time_50m: '50米用时',
  time_100m: '100米用时',
  turn_exit_time: '转身出水用时',
}

interface VideoPlayerProps {
  videoId: string
  fileName: string
  athleteName?: string
  athleteId?: string
  onBack: () => void
  onDerivedMetrics?: (metrics: Record<string, number>) => void
  showGuide?: boolean
}

const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2]

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  videoId,
  fileName,
  athleteName,
  athleteId,
  onBack,
  onDerivedMetrics,
  showGuide: initialGuide = false,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [speed, setSpeed] = useState(1)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [editAnnotation, setEditAnnotation] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [guideVisible, setGuideVisible] = useState(initialGuide)
  const [markers, setMarkers] = useState<any[]>([])
  const [derivedMetrics, setDerivedMetrics] = useState<Record<string, number>>({})
  const [showStats, setShowStats] = useState(false)
  const [savingToRecord, setSavingToRecord] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const [draggingProgress, setDraggingProgress] = useState(false)
  const [dragTime, setDragTime] = useState<number | null>(null)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
      if (e.key === 'Escape' && !isFullscreen) onBack()
      if (e.key === 'ArrowLeft' && videoRef.current) {
        videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - (e.shiftKey ? 0.01 : 1))
      }
      if (e.key === 'ArrowRight' && videoRef.current) {
        videoRef.current.currentTime = Math.min(duration, videoRef.current.currentTime + (e.shiftKey ? 0.01 : 1))
      }
      if (e.key === ' ') {
        e.preventDefault()
        if (videoRef.current) {
          if (videoRef.current.paused) videoRef.current.play()
          else videoRef.current.pause()
        }
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onBack, isFullscreen, duration])

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement)
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange)
  }, [])

  const dragTimeRef = useRef<number | null>(null)

  useEffect(() => {
    if (!draggingProgress) return
    const handleMove = (e: MouseEvent) => {
      if (!progressRef.current || !duration) return
      const rect = progressRef.current.getBoundingClientRect()
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
      const time = ratio * duration
      dragTimeRef.current = time
      setDragTime(time)
    }
    const handleUp = () => {
      if (dragTimeRef.current !== null && videoRef.current) {
        videoRef.current.currentTime = dragTimeRef.current
        setCurrentTime(dragTimeRef.current)
      }
      setDraggingProgress(false)
      setDragTime(null)
      dragTimeRef.current = null
    }
    document.addEventListener('mousemove', handleMove)
    document.addEventListener('mouseup', handleUp)
    return () => {
      document.removeEventListener('mousemove', handleMove)
      document.removeEventListener('mouseup', handleUp)
    }
  }, [draggingProgress, duration])

  const handleSpeedChange = (newSpeed: number) => {
    setSpeed(newSpeed)
    if (videoRef.current) videoRef.current.playbackRate = newSpeed
  }

  const handleFullscreen = () => {
    if (!containerRef.current) return
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      containerRef.current.requestFullscreen()
    }
  }

  const handleSeek = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
      setCurrentTime(time)
    }
  }, [])

  const handleTimeUpdate = useCallback(() => {
    if (draggingProgress) return
    if (videoRef.current) setCurrentTime(videoRef.current.currentTime)
  }, [draggingProgress])

  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) setDuration(videoRef.current.duration)
  }, [])

  const togglePlay = () => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play()
      setIsPlaying(true)
    } else {
      videoRef.current.pause()
      setIsPlaying(false)
    }
  }

  const stepFrame = (direction: number) => {
    if (!videoRef.current) return
    const fps = 30
    const step = 1 / fps
    videoRef.current.currentTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + direction * step))
    setCurrentTime(videoRef.current.currentTime)
  }

  const stepSecond = (direction: number) => {
    if (!videoRef.current) return
    videoRef.current.currentTime = Math.max(0, Math.min(duration, videoRef.current.currentTime + direction))
    setCurrentTime(videoRef.current.currentTime)
  }

  const handleProgressMouseDown = (e: React.MouseEvent) => {
    if (!progressRef.current || !duration) return
    setDraggingProgress(true)
    const rect = progressRef.current.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
    const time = ratio * duration
    setDragTime(time)
    if (videoRef.current) videoRef.current.currentTime = time
    setCurrentTime(time)
  }

  const handleDerivedFromTimeline = useCallback((derived: Record<string, number>) => {
    setDerivedMetrics(derived)
    if (onDerivedMetrics) onDerivedMetrics(derived)
  }, [onDerivedMetrics])

  const handleMarkersUpdate = useCallback((newMarkers: any[]) => {
    setMarkers(newMarkers)
    if (newMarkers.length > 0 && guideVisible) setGuideVisible(false)
  }, [guideVisible])

  const addMarker = async (type: MarkerTypeKey) => {
    if (!athleteId) { alert('请先关联运动员'); return }
    try {
      const res = await fetch(`${API_BASE}/video-markers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: videoId,
          athlete_id: athleteId,
          marker_type: type,
          marker_time: Math.round(currentTime * 100) / 100,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.derived_metrics) handleDerivedFromTimeline(data.derived_metrics)
        fetchMarkers()
        if (guideVisible) setGuideVisible(false)
      } else {
        const err = await res.json()
        alert(err.detail || '添加标记失败')
      }
    } catch { alert('网络错误') }
  }

  const fetchMarkers = async () => {
    try {
      const params = new URLSearchParams({ video_id: videoId })
      if (athleteId) params.set('athlete_id', athleteId)
      const res = await fetch(`${API_BASE}/video-markers?${params}`)
      if (res.ok) {
        const data = await res.json()
        setMarkers(data)
      }
    } catch {}
  }

  useEffect(() => { fetchMarkers() }, [videoId, athleteId])

  const deleteMarker = async (markerId: string) => {
    try {
      const res = await fetch(`${API_BASE}/video-markers/${markerId}`, { method: 'DELETE' })
      if (res.ok) {
        const data = await res.json()
        if (data.derived_metrics) handleDerivedFromTimeline(data.derived_metrics)
        fetchMarkers()
      }
    } catch {}
  }

  const saveToRecord = async () => {
    if (!derivedMetrics || Object.keys(derivedMetrics).length === 0) {
      alert('暂无派生指标数据，请先完成标记')
      return
    }
    setSavingToRecord(true)
    setSaveMessage('')
    try {
      const params = new URLSearchParams()
      if (athleteId) params.set('athlete_id', athleteId)
      const res = await fetch(`${API_BASE}/manual-records?${params}`)
      if (!res.ok) { setSaveMessage('查询记录失败'); return }
      const records = await res.json()
      const linked = records.filter((r: any) => r.video_id === videoId)
      if (linked.length === 0) {
        setSaveMessage('未找到关联此视频的比赛记录，请先在手动录入中创建记录并关联此视频')
        return
      }
      const target = linked[0]
      const metrics = target.metrics || {}
      const updated = { ...metrics }
      for (const [key, val] of Object.entries(derivedMetrics)) {
        if (updated[key]?.source === 'manual') continue
        updated[key] = { value: String(val), source: 'video_marker_calc' }
      }
      const updateRes = await fetch(`${API_BASE}/manual-records/${target.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: { metrics: updated }, version: target.version }),
      })
      if (updateRes.ok) {
        setSaveMessage('已保存到比赛记录')
      } else {
        const err = await updateRes.json()
        setSaveMessage(err.detail || '保存失败')
      }
    } catch {
      setSaveMessage('网络错误')
    } finally {
      setSavingToRecord(false)
    }
  }

  const formatTime = (t: number) => {
    const m = Math.floor(t / 60)
    const s = (t % 60).toFixed(2)
    return m > 0 ? `${m}:${s.padStart(5, '0')}` : `${s}s`
  }

  const displayTime = draggingProgress && dragTime !== null ? dragTime : currentTime
  const progressPct = duration ? (displayTime / duration) * 100 : 0

  return (
    <div className="video-player-container" ref={containerRef}>
      <div className="video-player-header">
        <button className="btn btn-outline" onClick={onBack} style={{ marginRight: 12 }}>
          ← 返回列表
        </button>
        <div className="video-player-title">
          <strong>{fileName}</strong>
          {athleteName && <span style={{ marginLeft: 8, color: 'var(--text-secondary)', fontSize: '0.88rem' }}>{athleteName}</span>}
        </div>
      </div>

      {guideVisible && (
        <div style={{ background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: 6, padding: '8px 14px', margin: '8px 0', fontSize: '0.88rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>请在视频中标记关键时刻：使用下方标记按钮，在对应时间点点击添加标记</span>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem', marginLeft: 8 }} onClick={() => setGuideVisible(false)}>×</button>
        </div>
      )}

      <div className="video-player-wrapper" style={{ position: 'relative' }}>
        <video
          ref={videoRef}
          src={`${API_BASE}/videos/${videoId}/stream`}
          autoPlay
          playsInline
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          style={{ width: '100%', maxHeight: '70vh', display: 'block', background: '#000' }}
        >
          您的浏览器不支持视频播放
        </video>
        <VideoAnnotationOverlay
          videoId={videoId}
          athleteName={athleteName}
          videoRef={videoRef}
          editMode={editAnnotation}
        />
      </div>

      <div className="custom-player-controls">
        <div className="progress-bar-container" ref={progressRef} onMouseDown={handleProgressMouseDown} style={{ position: 'relative', height: 20, background: '#1e293b', borderRadius: 4, cursor: 'pointer', margin: '4px 0' }}>
          <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${progressPct}%`, background: 'var(--primary)', borderRadius: 4, pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', left: `${progressPct}%`, top: -2, width: 8, height: 24, background: '#fff', borderRadius: 4, transform: 'translateX(-50%)', pointerEvents: 'none', boxShadow: '0 0 4px rgba(0,0,0,0.5)' }} />
          {markers.map(m => {
            const mt = MARKER_TYPES.find(t => t.key === m.marker_type)
            const left = duration ? (m.marker_time / duration) * 100 : 0
            return (
              <div key={m.id} style={{ position: 'absolute', left: `${left}%`, top: 0, bottom: 0, width: 3, background: mt?.color || '#888', transform: 'translateX(-50%)', pointerEvents: 'none', zIndex: 2 }} title={`${mt?.label}: ${formatTime(m.marker_time)}`} />
            )
          })}
          <div style={{ position: 'absolute', right: 8, top: 2, fontSize: '0.68rem', color: '#94a3b8', pointerEvents: 'none' }}>
            {formatTime(displayTime)} / {formatTime(duration)}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
          <button className="player-ctrl-btn" onClick={togglePlay} title={isPlaying ? '暂停' : '播放'}>
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button className="player-ctrl-btn" onClick={() => stepSecond(-5)} title="后退5秒">-5s</button>
          <button className="player-ctrl-btn" onClick={() => stepSecond(-1)} title="后退1秒">-1s</button>
          <button className="player-ctrl-btn" onClick={() => stepFrame(-1)} title="后退1帧 (Shift+←)">◀帧</button>
          <button className="player-ctrl-btn" onClick={() => stepFrame(1)} title="前进1帧 (Shift+→)">帧▶</button>
          <button className="player-ctrl-btn" onClick={() => stepSecond(1)} title="前进1秒">+1s</button>
          <button className="player-ctrl-btn" onClick={() => stepSecond(5)} title="前进5秒">+5s</button>

          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 4px' }}>
            {formatTime(displayTime)}
          </span>

          <div style={{ display: 'flex', gap: 2, marginLeft: 4 }}>
            {SPEED_OPTIONS.map(s => (
              <button
                key={s}
                className={`speed-btn ${speed === s ? 'active' : ''}`}
                onClick={() => handleSpeedChange(s)}
              >
                {s}x
              </button>
            ))}
          </div>

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
            <button
              className={`btn ${editAnnotation ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setEditAnnotation(!editAnnotation)}
              style={{ fontSize: '0.78rem', padding: '3px 10px' }}
            >
              {editAnnotation ? '完成标注' : '添加标注'}
            </button>
            <button className="btn btn-outline" onClick={handleFullscreen} style={{ fontSize: '0.78rem', padding: '3px 10px' }}>
              {isFullscreen ? '退出全屏' : '全屏'}
            </button>
          </div>
        </div>
      </div>

      <TimelineMarker
        videoId={videoId}
        athleteId={athleteId}
        duration={duration}
        currentTime={currentTime}
        onSeek={handleSeek}
        onDerivedMetrics={handleDerivedFromTimeline}
        onMarkersUpdate={handleMarkersUpdate}
      />

      <div className="marker-stats-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
            标记统计
            {markers.length > 0 && <span style={{ fontWeight: 400, color: 'var(--text-secondary)', marginLeft: 6 }}>{markers.length}个标记</span>}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-outline" style={{ fontSize: '0.75rem', padding: '2px 8px' }} onClick={() => setShowStats(!showStats)}>
              {showStats ? '收起' : '查看统计'}
            </button>
            {Object.keys(derivedMetrics).length > 0 && (
              <button
                className="btn btn-primary"
                style={{ fontSize: '0.75rem', padding: '2px 10px' }}
                onClick={saveToRecord}
                disabled={savingToRecord}
              >
                {savingToRecord ? '保存中...' : '保存到记录'}
              </button>
            )}
          </div>
        </div>
        {saveMessage && <div style={{ fontSize: '0.78rem', color: saveMessage.includes('已保存') ? 'var(--success)' : 'var(--danger)', marginBottom: 4 }}>{saveMessage}</div>}
        {showStats && (
          <div style={{ background: '#f8fafc', borderRadius: 6, padding: 8, fontSize: '0.82rem' }}>
            {markers.length === 0 ? (
              <div style={{ color: 'var(--text-secondary)' }}>暂无标记，请使用上方标记按钮添加</div>
            ) : (
              <>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>标记时间点</div>
                  {markers.map(m => {
                    const mt = MARKER_TYPES.find(t => t.key === m.marker_type)
                    return (
                      <div key={m.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid #f1f5f9' }}>
                        <span><span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: mt?.color, marginRight: 6 }} />{mt?.label}</span>
                        <span>{formatTime(m.marker_time)} <button style={{ fontSize: '0.68rem', color: '#f87171', background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => deleteMarker(m.id)}>删除</button></span>
                      </div>
                    )
                  })}
                </div>
                {Object.keys(derivedMetrics).length > 0 && (
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>派生指标</div>
                    {Object.entries(derivedMetrics).map(([key, val]) => (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid #f1f5f9' }}>
                        <span>{METRIC_LABELS[key] || key}</span>
                        <span style={{ fontWeight: 600, color: 'var(--primary)' }}>{Number(val).toFixed(3)}秒</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
