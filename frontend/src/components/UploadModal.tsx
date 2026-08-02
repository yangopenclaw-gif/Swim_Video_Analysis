import React, { useState, useRef, useEffect } from 'react'
import { AthleteSelector } from './AthleteSelector'
import { CompetitionSelector } from './CompetitionSelector'
import { VideoUploader } from '../uploader'

const API_BASE = '/api'

interface Athlete {
  id: string
  name: string
  created_at: string | null
}

interface Competition {
  id: string
  competition_name: string
  competition_date: string
  competition_location: string
  pool_length: number
  race_distance: number
  stroke_type: string
  created_at: string | null
}

interface UploadModalProps {
  open: boolean
  onClose: () => void
  onUploaded: () => void
}

const UPLOAD_DRAFT_KEY = 'upload_modal_draft'

export const UploadModal: React.FC<UploadModalProps> = ({ open, onClose, onUploaded }) => {
  const [selectedAthlete, setSelectedAthlete] = useState<Athlete | null>(null)
  const [selectedCompetition, setSelectedCompetition] = useState<Competition | null>(null)
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadSpeed, setUploadSpeed] = useState(0)
  const [uploadEta, setUploadEta] = useState(0)
  const [uploadUploaded, setUploadUploaded] = useState(0)
  const [uploadTotal, setUploadTotal] = useState(0)
  const [error, setError] = useState('')
  const uploaderRef = useRef<VideoUploader | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      const raw = localStorage.getItem(UPLOAD_DRAFT_KEY)
      if (raw) {
        try {
          const draft = JSON.parse(raw)
          if (draft.athleteName) {
            setSelectedAthlete({ id: draft.athleteId || '', name: draft.athleteName, created_at: null })
          }
        } catch {}
      }
    }
  }, [open])

  useEffect(() => {
    if (selectedAthlete || selectedCompetition) {
      localStorage.setItem(UPLOAD_DRAFT_KEY, JSON.stringify({
        athleteId: selectedAthlete?.id,
        athleteName: selectedAthlete?.name,
        competitionId: selectedCompetition?.id,
      }))
    }
  }, [selectedAthlete, selectedCompetition])

  if (!open) return null

  const canUpload = !!selectedAthlete && !!selectedCompetition && !!videoFile && !uploading

  const missingSteps: string[] = []
  if (!selectedAthlete) missingSteps.push('选择运动员')
  if (!selectedCompetition) missingSteps.push('选择比赛信息')
  if (!videoFile) missingSteps.push('选择视频文件')

  const handleUpload = async () => {
    if (!selectedAthlete || !selectedCompetition || !videoFile) return
    setError('')
    setUploading(true)
    setUploadProgress(0)
    setUploadSpeed(0)
    setUploadEta(0)
    setUploadUploaded(0)
    setUploadTotal(videoFile.size)

    try {
      const uploader = new VideoUploader({
        onProgress: (pct: number, uploaded: number, total: number) => {
          setUploadProgress(pct)
          setUploadUploaded(uploaded)
          setUploadTotal(total)
        },
        onSpeed: (speed: number) => {
          setUploadSpeed(speed)
        },
        onEta: (eta: number) => {
          setUploadEta(eta)
        },
        onStatus: () => {},
        onComplete: (_taskId: string) => {
          setUploading(false)
          setUploadProgress(100)
          setVideoFile(null)
          onUploaded()
          onClose()
        },
        onError: (err: string) => {
          setError(err || '上传失败')
          setUploading(false)
        },
      })
      uploaderRef.current = uploader
      await uploader.upload(
        videoFile,
        selectedAthlete.name,
        selectedCompetition.pool_length,
        selectedCompetition.race_distance,
        1,

      )
    } catch (e: any) {
      setError(e.message || '上传失败')
      setUploading(false)
    }
  }

  const handleClose = () => {
    if (uploading) return
    setVideoFile(null)
    setUploadProgress(0)
    setError('')
    onClose()
  }

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 560, borderRadius: 'var(--radius)', padding: '24px 20px' }}>
        <h2 style={{ marginBottom: 16 }}>上传视频</h2>

        <AthleteSelector
          selectedAthleteId={selectedAthlete?.id || null}
          onSelect={setSelectedAthlete}
        />

        <CompetitionSelector
          selectedCompetitionId={selectedCompetition?.id || null}
          onSelect={setSelectedCompetition}
        />

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 6, fontSize: '0.92rem' }}>视频文件</div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp4,.avi,.mov,.mkv,.webm"
            onChange={e => { setVideoFile(e.target.files?.[0] || null) }}
            style={{ display: 'none' }}
          />
          <button
            className="btn btn-outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            style={{ width: '100%', textAlign: 'left' }}
          >
            {videoFile ? `📁 ${videoFile.name} (${(videoFile.size / 1024 / 1024).toFixed(1)}MB)` : '📁 点击选择视频文件 (.mp4/.avi/.mov/.mkv/.webm)'}
          </button>
        </div>

        {uploading && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ background: 'var(--bg)', borderRadius: 'var(--radius-sm)', overflow: 'hidden', height: 10 }}>
              <div style={{ width: `${uploadProgress}%`, background: 'linear-gradient(90deg, var(--primary), var(--accent))', height: '100%', transition: 'width 0.3s' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: '0.78rem', color: 'var(--text-secondary)', flexWrap: 'wrap', gap: 4 }}>
              <span>{uploadProgress.toFixed(1)}%</span>
              <span>{(uploadUploaded / 1024 / 1024).toFixed(1)} / {(uploadTotal / 1024 / 1024).toFixed(1)} MB</span>
              <span>{uploadSpeed > 0 ? `${(uploadSpeed / 1024 / 1024).toFixed(1)} MB/s` : '计算中...'}</span>
              <span>{uploadEta > 0 ? `剩余${uploadEta > 60 ? `${Math.floor(uploadEta / 60)}分${Math.round(uploadEta % 60)}秒` : `${Math.round(uploadEta)}秒`}` : ''}</span>
            </div>
          </div>
        )}

        {!canUpload && !uploading && missingSteps.length > 0 && (
          <div style={{ padding: '8px 12px', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 'var(--radius-sm)', marginBottom: 12, fontSize: '0.82rem', color: '#92400e' }}>
            还需完成: {missingSteps.join(' → ')}
          </div>
        )}

        {error && <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: 8, padding: '8px 12px', background: '#fef2f2', borderRadius: 'var(--radius-sm)' }}>{error}</p>}

        <div className="modal-actions" style={{ marginTop: 16 }}>
          <button className="btn btn-outline" onClick={handleClose} disabled={uploading}>取消</button>
          <button
            className="btn btn-primary"
            onClick={handleUpload}
            disabled={!canUpload}
            style={{ minWidth: 120 }}
          >
            {uploading ? `上传中 ${uploadProgress.toFixed(0)}%` : '开始上传'}
          </button>
        </div>
      </div>
    </div>
  )
}
