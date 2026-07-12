import React, { useState, useEffect } from 'react'

const API_BASE = '/api'

interface Athlete {
  id: string
  name: string
  created_at: string | null
}

interface AthleteSelectorProps {
  selectedAthleteId: string | null
  onSelect: (athlete: Athlete) => void
}

export const AthleteSelector: React.FC<AthleteSelectorProps> = ({ selectedAthleteId, onSelect }) => {
  const [athletes, setAthletes] = useState<Athlete[]>([])
  const [newName, setNewName] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => { fetchAthletes() }, [])

  const fetchAthletes = async () => {
    try {
      const res = await fetch(`${API_BASE}/athletes`)
      if (res.ok) {
        const data = await res.json()
        setAthletes(data)
      }
    } catch (e) { console.error('fetchAthletes error', e) }
  }

  const handleCreate = async () => {
    setError('')
    if (!newName.trim()) { setError('请输入运动员姓名'); return }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/athletes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName.trim() }),
      })
      if (res.ok) {
        const athlete = await res.json()
        setAthletes(prev => [...prev, athlete])
        setNewName('')
        setShowNew(false)
        onSelect(athlete)
      } else {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail || ''
        if (res.status === 405) {
          setError(`请求被拒绝(405 Method Not Allowed) - 请重启后端服务器！URL: ${API_BASE}/athletes, 方法: POST`)
        } else {
          setError(detail || `创建失败(${res.status}) URL: ${API_BASE}/athletes`)
        }
      }
    } catch (e: any) {
      setError(`网络错误: ${e.message || ''} URL: ${API_BASE}/athletes`)
    } finally {
      setLoading(false)
    }
  }

  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    const athlete = athletes.find(a => a.id === id)
    if (athlete) onSelect(athlete)
  }

  const selectedName = athletes.find(a => a.id === selectedAthleteId)?.name

  return (
    <div className="card" style={{ marginBottom: 8, padding: '10px 12px' }}>
      <div style={{ fontWeight: 700, marginBottom: 8, fontSize: '0.92rem' }}>运动员</div>

      {selectedName && (
        <div style={{ marginBottom: 8, padding: '6px 12px', background: 'var(--primary-light)', borderRadius: 'var(--radius-sm)', fontSize: '0.88rem' }}>
          已选择: <strong>{selectedName}</strong>
        </div>
      )}

      <div className="form-row">
        <div className="form-group" style={{ flex: 2 }}>
          <select
            value={selectedAthleteId || ''}
            onChange={handleSelect}
            className="form-group"
            style={{ width: '100%', padding: '10px 14px', fontSize: '0.95rem', border: '2px solid var(--border)', borderRadius: 'var(--radius-sm)', minHeight: 44 }}
          >
            <option value="">-- 请选择运动员 --</option>
            {athletes.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
        <button
          className={`btn ${showNew ? 'btn-outline' : 'btn-primary'}`}
          onClick={() => setShowNew(!showNew)}
          style={{ flex: '0 0 auto' }}
        >
          {showNew ? '取消新建' : '+ 新建运动员'}
        </button>
      </div>

      {showNew && (
        <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="输入运动员姓名"
            autoFocus
            onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
            style={{ flex: 1, padding: '10px 14px', fontSize: '0.95rem', border: '2px solid var(--border)', borderRadius: 'var(--radius-sm)', minHeight: 44, outline: 'none' }}
          />
          <button
            className="btn btn-success"
            onClick={handleCreate}
            disabled={loading || !newName.trim()}
          >
            {loading ? '创建中...' : '创建'}
          </button>
        </div>
      )}

      {error && <p style={{ color: 'var(--danger)', margin: '6px 0 0', fontSize: '0.82rem' }}>{error}</p>}
    </div>
  )
}
