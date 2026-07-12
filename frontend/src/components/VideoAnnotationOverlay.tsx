import React, { useState, useRef, useEffect, useCallback } from 'react'

const API_BASE = '/api'

interface Annotation {
  id: string
  video_id: string
  athlete_id?: string
  annotation_type: string
  position_x: number
  position_y: number
  width: number
  height: number
  label_text?: string
  video_time: number
}

interface VideoAnnotationOverlayProps {
  videoId: string
  athleteName?: string
  videoRef: React.RefObject<HTMLVideoElement>
  editMode: boolean
}

export const VideoAnnotationOverlay: React.FC<VideoAnnotationOverlayProps> = ({
  videoId,
  athleteName,
  videoRef,
  editMode,
}) => {
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [dragging, setDragging] = useState<string | null>(null)
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 })
  const overlayRef = useRef<HTMLDivElement>(null)

  const fetchAnnotations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/video-annotations?video_id=${videoId}`)
      if (res.ok) setAnnotations(await res.json())
    } catch {}
  }, [videoId])

  useEffect(() => { fetchAnnotations() }, [fetchAnnotations])

  const getOverlaySize = () => {
    if (!overlayRef.current) return { w: 0, h: 0 }
    return { w: overlayRef.current.clientWidth, h: overlayRef.current.clientHeight }
  }

  const handleMouseDown = (e: React.MouseEvent, ann: Annotation) => {
    if (!editMode) return
    e.preventDefault()
    e.stopPropagation()
    const { w, h } = getOverlaySize()
    setDragOffset({ x: e.clientX - ann.position_x * w, y: e.clientY - ann.position_y * h })
    setDragging(ann.id)
  }

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!dragging) return
    const { w, h } = getOverlaySize()
    const newX = Math.max(0, Math.min(1, (e.clientX - dragOffset.x) / w))
    const newY = Math.max(0, Math.min(1, (e.clientY - dragOffset.y) / h))
    setAnnotations(prev => prev.map(a => a.id === dragging ? { ...a, position_x: newX, position_y: newY } : a))
  }, [dragging, dragOffset])

  const handleMouseUp = useCallback(async () => {
    if (!dragging) return
    const ann = annotations.find(a => a.id === dragging)
    if (ann) {
      try {
        await fetch(`${API_BASE}/video-annotations/${ann.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ position_x: ann.position_x, position_y: ann.position_y }),
        })
      } catch {}
    }
    setDragging(null)
  }, [dragging, annotations])

  useEffect(() => {
    if (dragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [dragging, handleMouseMove, handleMouseUp])

  const handleAddBox = async () => {
    try {
      const res = await fetch(`${API_BASE}/video-annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: videoId,
          annotation_type: 'bounding_box',
          position_x: 0.4, position_y: 0.3,
          width: 0.2, height: 0.3,
          label_text: athleteName || '运动员',
          video_time: videoRef.current?.currentTime || 0,
        }),
      })
      if (res.ok) fetchAnnotations()
    } catch {}
  }

  const handleAddLabel = async () => {
    try {
      const res = await fetch(`${API_BASE}/video-annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: videoId,
          annotation_type: 'name_label',
          position_x: 0.45, position_y: 0.25,
          width: 0.1, height: 0.05,
          label_text: athleteName || '运动员',
          video_time: videoRef.current?.currentTime || 0,
        }),
      })
      if (res.ok) fetchAnnotations()
    } catch {}
  }

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/video-annotations/${id}`, { method: 'DELETE' })
      if (res.ok) setAnnotations(prev => prev.filter(a => a.id !== id))
    } catch {}
  }

  return (
    <div style={{ position: 'relative' }}>
      {editMode && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#f97316' }}>标注模式:</span>
          <button className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '4px 10px' }} onClick={handleAddBox}>
            + 标识框
          </button>
          <button className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '4px 10px' }} onClick={handleAddLabel}>
            + 姓名标签
          </button>
          <button className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '4px 10px' }} onClick={async () => {
            try {
              const res = await fetch(`${API_BASE}/video-annotations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  video_id: videoId,
                  annotation_type: 'tracking_mark',
                  position_x: 0.5, position_y: 0.5,
                  video_time: videoRef.current?.currentTime || 0,
                }),
              })
              if (res.ok) fetchAnnotations()
            } catch {}
          }}>
            + 跟踪标记
          </button>
        </div>
      )}
      <div
        ref={overlayRef}
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: editMode ? 'auto' : 'none', zIndex: 10 }}
      >
        {annotations.map(ann => {
          const style: React.CSSProperties = {
            position: 'absolute',
            left: `${ann.position_x * 100}%`,
            top: `${ann.position_y * 100}%`,
            cursor: editMode ? 'move' : 'default',
          }

          if (ann.annotation_type === 'bounding_box') {
            return (
              <div key={ann.id} style={{ ...style, width: `${ann.width * 100}%`, height: `${ann.height * 100}%`, border: '2px solid #facc15', borderRadius: 4, background: 'rgba(250, 204, 21, 0.08)' }}
                onMouseDown={e => handleMouseDown(e, ann)}>
                {ann.label_text && (
                  <span style={{ position: 'absolute', top: -20, left: 0, background: 'rgba(0,0,0,0.7)', color: '#facc15', fontSize: '0.72rem', padding: '1px 6px', borderRadius: 3, whiteSpace: 'nowrap' }}>
                    {ann.label_text}
                  </span>
                )}
                {editMode && (
                  <button onClick={() => handleDelete(ann.id)} style={{ position: 'absolute', top: -8, right: -8, background: '#ef4444', color: '#fff', border: 'none', borderRadius: '50%', width: 16, height: 16, fontSize: '0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>×</button>
                )}
              </div>
            )
          }

          if (ann.annotation_type === 'name_label') {
            return (
              <div key={ann.id} style={{ ...style }}
                onMouseDown={e => handleMouseDown(e, ann)}>
                <span style={{ background: 'rgba(37,99,235,0.85)', color: '#fff', fontSize: '0.75rem', padding: '2px 8px', borderRadius: 4, whiteSpace: 'nowrap' }}>
                  {ann.label_text || '运动员'}
                </span>
                {editMode && (
                  <button onClick={() => handleDelete(ann.id)} style={{ marginLeft: 4, background: '#ef4444', color: '#fff', border: 'none', borderRadius: '50%', width: 14, height: 14, fontSize: '0.55rem', cursor: 'pointer', verticalAlign: 'middle' }}>×</button>
                )}
              </div>
            )
          }

          if (ann.annotation_type === 'tracking_mark') {
            return (
              <div key={ann.id} style={{ ...style, width: 8, height: 8, borderRadius: '50%', background: '#22c55e', border: '2px solid #fff', boxShadow: '0 0 4px rgba(0,0,0,0.5)' }}
                onMouseDown={e => handleMouseDown(e, ann)}>
                {editMode && (
                  <button onClick={() => handleDelete(ann.id)} style={{ position: 'absolute', top: -8, right: -8, background: '#ef4444', color: '#fff', border: 'none', borderRadius: '50%', width: 14, height: 14, fontSize: '0.55rem', cursor: 'pointer' }}>×</button>
                )}
              </div>
            )
          }
          return null
        })}
      </div>

    </div>
  )
}