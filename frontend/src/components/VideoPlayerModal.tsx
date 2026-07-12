import React, { useEffect, useRef } from 'react'

const API_BASE = '/api'

interface VideoPlayerModalProps {
  open: boolean
  videoId: string | null
  fileName?: string
  onClose: () => void
}

export const VideoPlayerModal: React.FC<VideoPlayerModalProps> = ({
  open,
  videoId,
  fileName,
  onClose,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open && videoRef.current) {
      videoRef.current.pause()
    }
  }, [open])

  if (!open || !videoId) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content video-player-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{fileName || '视频播放'}</h3>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body" style={{ padding: 0, background: '#000' }}>
          <video
            ref={videoRef}
            src={`${API_BASE}/videos/${videoId}/stream`}
            controls
            autoPlay
            playsInline
            style={{ width: '100%', maxHeight: '75vh', display: 'block' }}
          >
            您的浏览器不支持视频播放
          </video>
        </div>
      </div>
    </div>
  )
}