import React, { useEffect, useState, useCallback, useRef } from 'react'

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

interface MarkerData {
  id: string
  video_id: string
  athlete_id: string
  marker_type: MarkerTypeKey
  marker_time: number
  athlete_name?: string
}

interface TimelineMarkerProps {
  videoId: string
  athleteId?: string
  duration: number
  currentTime: number
  onSeek: (time: number) => void
  onDerivedMetrics?: (metrics: Record<string, number>) => void
  onMarkersUpdate?: (markers: MarkerData[]) => void
}

export const TimelineMarker: React.FC<TimelineMarkerProps> = ({
  videoId,
  athleteId,
  duration,
  currentTime,
  onSeek,
  onDerivedMetrics,
  onMarkersUpdate,
}) => {
  const [markers, setMarkers] = useState<MarkerData[]>([])
  const [activeAddType, setActiveAddType] = useState<MarkerTypeKey | null>(null)
  const [hoveredMarker, setHoveredMarker] = useState<string | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const trackRef = useRef<HTMLDivElement>(null)

  const fetchMarkers = useCallback(async () => {
    try {
      const params = new URLSearchParams({ video_id: videoId })
      if (athleteId) params.set('athlete_id', athleteId)
      const res = await fetch(`${API_BASE}/video-markers?${params}`)
      if (res.ok) {
        const data = await res.json()
        setMarkers(data)
        if (onMarkersUpdate) onMarkersUpdate(data)
      }
    } catch {}
  }, [videoId, athleteId])

  useEffect(() => { fetchMarkers() }, [fetchMarkers])

  const addMarker = async (type: MarkerTypeKey) => {
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
        if (data.derived_metrics && onDerivedMetrics) {
          onDerivedMetrics(data.derived_metrics)
        }
        await fetchMarkers()
      } else {
        const err = await res.json()
        alert(err.detail || '添加标记失败')
      }
    } catch {
      alert('网络错误')
    }
    setActiveAddType(null)
  }

  const updateMarkerTime = async (markerId: string, newTime: number) => {
    try {
      const res = await fetch(`${API_BASE}/video-markers/${markerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ marker_time: Math.round(newTime * 100) / 100 }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.derived_metrics && onDerivedMetrics) {
          onDerivedMetrics(data.derived_metrics)
        }
        await fetchMarkers()
      }
    } catch {}
  }

  const deleteMarker = async (markerId: string) => {
    try {
      const res = await fetch(`${API_BASE}/video-markers/${markerId}`, { method: 'DELETE' })
      if (res.ok) {
        const data = await res.json()
        if (data.derived_metrics && onDerivedMetrics) {
          onDerivedMetrics(data.derived_metrics)
        }
        await fetchMarkers()
      }
    } catch {}
  }

  const handleTrackMouseDown = (e: React.MouseEvent) => {
    if (!trackRef.current || !duration) return
    const rect = trackRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const ratio = x / rect.width
    const time = ratio * duration
    onSeek(time)
  }

  const handleMarkerMouseDown = (e: React.MouseEvent, markerId: string) => {
    e.stopPropagation()
    setDragging(markerId)
    let latestTime: number | null = null
    const handleMove = (ev: MouseEvent) => {
      if (!trackRef.current || !duration) return
      const rect = trackRef.current.getBoundingClientRect()
      const x = ev.clientX - rect.left
      const ratio = Math.max(0, Math.min(1, x / rect.width))
      const newTime = ratio * duration
      latestTime = newTime
      setMarkers(prev => prev.map(m => m.id === markerId ? { ...m, marker_time: newTime } : m))
    }
    const handleUp = () => {
      setDragging(null)
      if (latestTime != null) updateMarkerTime(markerId, latestTime)
      document.removeEventListener('mousemove', handleMove)
      document.removeEventListener('mouseup', handleUp)
    }
    document.addEventListener('mousemove', handleMove)
    document.addEventListener('mouseup', handleUp)
  }

  const formatTime = (t: number) => {
    const m = Math.floor(t / 60)
    const s = (t % 60).toFixed(2)
    return m > 0 ? `${m}:${s.padStart(5, '0')}` : `${s}s`
  }

  if (!duration) return null

  return (
    <div className="timeline-marker-container">
      <div className="marker-type-buttons">
        {MARKER_TYPES.map(mt => (
          <button
            key={mt.key}
            className={`marker-type-btn ${activeAddType === mt.key ? 'active' : ''}`}
            style={{ borderColor: mt.color, color: activeAddType === mt.key ? '#fff' : mt.color, backgroundColor: activeAddType === mt.key ? mt.color : 'transparent' }}
            onClick={() => {
              if (activeAddType === mt.key) {
                setActiveAddType(null)
              } else {
                if (!athleteId) { alert('请先关联运动员'); return }
                addMarker(mt.key)
              }
            }}
            title={`在当前时刻添加${mt.label}标记`}
          >
            {mt.label}
          </button>
        ))}
      </div>
      <div
        className="timeline-track"
        ref={trackRef}
        onClick={handleTrackMouseDown}
        style={{ position: 'relative', height: 28, background: '#1e293b', borderRadius: 6, cursor: 'pointer', margin: '4px 0' }}
      >
        <div
          style={{ position: 'absolute', left: `${(currentTime / duration) * 100}%`, top: 0, bottom: 0, width: 2, background: '#fff', zIndex: 5, pointerEvents: 'none' }}
        />
        {markers.map(m => {
          const mt = MARKER_TYPES.find(t => t.key === m.marker_type)
          const left = (m.marker_time / duration) * 100
          return (
            <div
              key={m.id}
              style={{ position: 'absolute', left: `${left}%`, top: 0, bottom: 0, zIndex: 10, cursor: dragging === m.id ? 'grabbing' : 'grab', transform: 'translateX(-50%)' }}
              onMouseDown={e => handleMarkerMouseDown(e, m.id)}
              onMouseEnter={() => setHoveredMarker(m.id)}
              onMouseLeave={() => setHoveredMarker(null)}
              onClick={e => e.stopPropagation()}
            >
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: mt?.color || '#888', margin: '9px auto 0', border: '2px solid #fff', boxShadow: '0 0 4px rgba(0,0,0,0.5)' }} />
              {hoveredMarker === m.id && (
                <div style={{
                  position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
                  background: 'rgba(0,0,0,0.9)', color: '#fff', padding: '4px 8px', borderRadius: 4,
                  fontSize: '0.75rem', whiteSpace: 'nowrap', marginBottom: 4, zIndex: 20,
                }}>
                  <div>{mt?.label}: {formatTime(m.marker_time)}</div>
                  {m.athlete_name && <div style={{ fontSize: '0.68rem', opacity: 0.8 }}>{m.athlete_name}</div>}
                  <button
                    style={{ fontSize: '0.68rem', color: '#f87171', background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginTop: 2 }}
                    onClick={() => { if (confirm('删除此标记？')) deleteMarker(m.id) }}
                  >删除</button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}