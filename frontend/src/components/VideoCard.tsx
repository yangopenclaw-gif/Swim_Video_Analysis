import React, { useState } from 'react'

const API_BASE = '/api'

interface VideoCardProps {
  id: string
  fileName: string
  athleteName?: string
  competitionName?: string
  uploadTime?: string
  hasAthlete?: boolean
  hasCompetition?: boolean
  onPlay?: (id: string) => void
  onRefresh?: () => void
}

export const VideoCard: React.FC<VideoCardProps> = ({
  id,
  fileName,
  athleteName,
  competitionName,
  uploadTime,
  hasAthlete,
  hasCompetition,
  onPlay,
  onRefresh,
}) => {
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState(fileName)
  const [showAssoc, setShowAssoc] = useState(false)
  const [athletes, setAthletes] = useState<any[]>([])
  const [competitions, setCompetitions] = useState<any[]>([])
  const [selAthlete, setSelAthlete] = useState('')
  const [selComp, setSelComp] = useState('')

  const handleRename = async () => {
    if (!editName.trim()) { setEditName(fileName); setEditing(false); return }
    try {
      const res = await fetch(`${API_BASE}/videos/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ display_name: editName.trim() }),
      })
      if (res.ok && onRefresh) onRefresh()
    } catch {}
    setEditing(false)
  }

  const handleOpenAssoc = async () => {
    setShowAssoc(true)
    try {
      const [aRes, cRes] = await Promise.all([
        fetch(`${API_BASE}/athletes`),
        fetch(`${API_BASE}/competitions`),
      ])
      if (aRes.ok) setAthletes(await aRes.json())
      if (cRes.ok) setCompetitions(await cRes.json())
    } catch {}
  }

  const handleSaveAssoc = async () => {
    try {
      const body: any = {}
      if (selAthlete) body.athlete_id = selAthlete
      if (selComp) body.competition_id = selComp
      const res = await fetch(`${API_BASE}/videos/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        setShowAssoc(false)
        if (onRefresh) onRefresh()
      }
    } catch {}
  }

  return (
    <div className="video-card">
      <div className="video-card-thumb" onClick={() => onPlay?.(id)} style={{ cursor: 'pointer' }}>
        <img
          src={`${API_BASE}/videos/${id}/thumbnail`}
          alt={fileName}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none'
            const parent = (e.target as HTMLImageElement).parentElement
            if (parent) parent.innerHTML = '🎬'
          }}
        />
        <div className="play-overlay">▶</div>
      </div>
      <div className="video-card-info">
        <div className="video-card-name-row">
          {editing ? (
            <input
              value={editName}
              onChange={e => setEditName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleRename(); if (e.key === 'Escape') { setEditName(fileName); setEditing(false) } }}
              onBlur={handleRename}
              autoFocus
              style={{ flex: 1, padding: '2px 6px', fontSize: '0.85rem', border: '1px solid var(--primary)', borderRadius: 4, outline: 'none' }}
            />
          ) : (
            <span className="athlete-name" style={{ flex: 1 }}>{fileName}</span>
          )}
          <button
            className="card-action-btn"
            onClick={() => { setEditName(fileName); setEditing(!editing) }}
            title="重命名"
          >✏️</button>
        </div>
        <div className="comp-name">
          {athleteName || '未关联运动员'}
          <button className="inline-link" onClick={handleOpenAssoc}>{hasAthlete ? '修改' : '关联'}</button>
        </div>
        <div className="comp-name">
          {competitionName || '未关联比赛'}
          <button className="inline-link" onClick={handleOpenAssoc}>{hasCompetition ? '修改' : '关联'}</button>
        </div>
        {uploadTime && (
          <div className="upload-time">{new Date(uploadTime).toLocaleString()}</div>
        )}
      </div>

      {showAssoc && (
        <div className="assoc-panel">
          <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 6 }}>关联运动员/比赛</div>
          <select value={selAthlete} onChange={e => setSelAthlete(e.target.value)} className="assoc-select">
            <option value="">选择运动员</option>
            {athletes.map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select value={selComp} onChange={e => setSelComp(e.target.value)} className="assoc-select">
            <option value="">选择比赛</option>
            {competitions.map((c: any) => <option key={c.id} value={c.id}>{c.competition_name}</option>)}
          </select>
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            <button className="btn btn-primary" style={{ fontSize: '0.78rem', padding: '4px 10px' }} onClick={handleSaveAssoc}>保存</button>
            <button className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '4px 10px' }} onClick={() => setShowAssoc(false)}>取消</button>
          </div>
        </div>
      )}
    </div>
  )
}
