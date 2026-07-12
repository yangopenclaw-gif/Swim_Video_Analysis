import React, { useState, useEffect } from 'react'
import { VideoCard } from './VideoCard'
import { UploadModal } from './UploadModal'
import { VideoPlayer } from './VideoPlayer'

const API_BASE = '/api'

type CategoryType = 'by_athlete' | 'by_competition' | 'all'

interface VideoInfo {
  id: string
  file_name: string
  display_name?: string
  athlete_name?: string
  competition_name?: string
  upload_time?: string
  athlete_id?: string
  competition_id?: string
}

export const VideoAppreciationPage: React.FC = () => {
  const [videos, setVideos] = useState<VideoInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState<CategoryType>('by_athlete')
  const [showUpload, setShowUpload] = useState(false)
  const [playingVideo, setPlayingVideo] = useState<VideoInfo | null>(null)

  useEffect(() => {
    fetchVideos()
  }, [])

  const fetchVideos = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/videos`)
      if (res.ok) {
        const data = await res.json()
        setVideos(data)
      }
    } catch {} finally {
      setLoading(false)
    }
  }

  const handlePlay = (id: string) => {
    const v = videos.find(v => v.id === id)
    if (v) setPlayingVideo(v)
  }

  const handleRefresh = () => {
    fetchVideos()
  }

  const groupedByAthlete = () => {
    const groups: Record<string, VideoInfo[]> = {}
    for (const v of videos) {
      const name = v.athlete_name || '未关联运动员'
      if (!groups[name]) groups[name] = []
      groups[name].push(v)
    }
    return groups
  }

  const groupedByCompetition = () => {
    const groups: Record<string, VideoInfo[]> = {}
    for (const v of videos) {
      const name = v.competition_name || '未关联比赛'
      if (!groups[name]) groups[name] = []
      groups[name].push(v)
    }
    return groups
  }

  const renderGrouped = (groups: Record<string, VideoInfo[]>) => (
    Object.entries(groups).map(([name, items]) => (
      <div key={name}>
        <div className="group-header">{name} ({items.length})</div>
        <div className="video-grid">
          {items.map(v => (
            <VideoCard
              key={v.id}
              id={v.id}
              fileName={v.display_name || v.file_name}
              athleteName={v.athlete_name}
              competitionName={v.competition_name}
              uploadTime={v.upload_time}
              hasAthlete={!!v.athlete_id}
              hasCompetition={!!v.competition_id}
              onPlay={handlePlay}
              onRefresh={handleRefresh}
            />
          ))}
        </div>
      </div>
    ))
  )

  if (playingVideo) {
    return (
      <VideoPlayer
        videoId={playingVideo.id}
        fileName={playingVideo.display_name || playingVideo.file_name}
        athleteName={playingVideo.athlete_name}
        athleteId={playingVideo.athlete_id}
        onBack={() => setPlayingVideo(null)}
      />
    )
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div className="category-tabs">
          {([
            { key: 'by_athlete', label: '按运动员' },
            { key: 'by_competition', label: '按比赛' },
            { key: 'all', label: '全部' },
          ] as { key: CategoryType; label: string }[]).map(cat => (
            <button
              key={cat.key}
              className={`category-tab ${category === cat.key ? 'active' : ''}`}
              onClick={() => setCategory(cat.key)}
            >
              {cat.label}
            </button>
          ))}
        </div>
        <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
          上传视频
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <div className="spinner" />
          <p>加载中...</p>
        </div>
      ) : videos.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="icon">🎥</div>
            <p>暂无视频，点击上传按钮添加比赛视频</p>
          </div>
        </div>
      ) : category === 'by_athlete' ? (
        renderGrouped(groupedByAthlete())
      ) : category === 'by_competition' ? (
        renderGrouped(groupedByCompetition())
      ) : (
        <div className="video-grid">
          {videos.map(v => (
            <VideoCard
              key={v.id}
              id={v.id}
              fileName={v.display_name || v.file_name}
              athleteName={v.athlete_name}
              competitionName={v.competition_name}
              uploadTime={v.upload_time}
              hasAthlete={!!v.athlete_id}
              hasCompetition={!!v.competition_id}
              onPlay={handlePlay}
              onRefresh={handleRefresh}
            />
          ))}
        </div>
      )}

      <UploadModal
        open={showUpload}
        onClose={() => setShowUpload(false)}
        onUploaded={fetchVideos}
      />
    </div>
  )
}
