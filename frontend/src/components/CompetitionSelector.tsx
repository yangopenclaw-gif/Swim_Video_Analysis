import React, { useState, useEffect } from 'react'

const API_BASE = '/api'

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

interface CompetitionSelectorProps {
  selectedCompetitionId: string | null
  onSelect: (competition: Competition) => void
}

export const CompetitionSelector: React.FC<CompetitionSelectorProps> = ({ selectedCompetitionId, onSelect }) => {
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [showNew, setShowNew] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({
    competition_name: '',
    competition_date: '',
    competition_location: '',
    pool_length: 50,
    race_distance: 100,
    stroke_type: '自由泳',
  })

  useEffect(() => { fetchCompetitions() }, [])

  const fetchCompetitions = async () => {
    try {
      const res = await fetch(`${API_BASE}/competitions`)
      if (res.ok) setCompetitions(await res.json())
    } catch (e) { console.error('fetchCompetitions error', e) }
  }

  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value
    if (id === '__new__') {
      setShowNew(true)
      setForm({ competition_name: '', competition_date: '', competition_location: '', pool_length: 50, race_distance: 100, stroke_type: '自由泳' })
      return
    }
    setShowNew(false)
    const comp = competitions.find(c => c.id === id)
    if (comp) onSelect(comp)
  }

  const handleCreate = async () => {
    setError('')
    if (!form.competition_name.trim()) { setError('比赛名称不能为空'); return }
    if (!form.competition_date.trim()) { setError('比赛日期不能为空'); return }
    if (!form.competition_location.trim()) { setError('比赛地点不能为空'); return }
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/competitions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (res.ok) {
        const comp = await res.json()
        setCompetitions(prev => [comp, ...prev])
        setShowNew(false)
        onSelect(comp)
      } else {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail || ''
        if (res.status === 405) {
          setError(`请求被拒绝(405 Method Not Allowed) - 请重启后端服务器！URL: ${API_BASE}/competitions, 方法: POST`)
        } else {
          setError(detail || `创建失败(${res.status}) URL: ${API_BASE}/competitions`)
        }
      }
    } catch (e: any) {
      setError(`网络错误: ${e.message || ''} URL: ${API_BASE}/competitions`)
    } finally {
      setLoading(false)
    }
  }

  const selectedComp = competitions.find(c => c.id === selectedCompetitionId)

  return (
    <div className="card" style={{ marginBottom: 8, padding: '10px 12px' }}>
      <div style={{ fontWeight: 700, marginBottom: 8, fontSize: '0.92rem' }}>比赛信息</div>

      {selectedComp && (
        <div style={{ marginBottom: 8, padding: '6px 12px', background: 'var(--primary-light)', borderRadius: 'var(--radius-sm)', fontSize: '0.88rem' }}>
          已选择: <strong>{selectedComp.competition_name}</strong> ({selectedComp.pool_length}m池{selectedComp.race_distance}m)
        </div>
      )}

      <div className="form-row">
        <div className="form-group" style={{ flex: 2 }}>
          <select
            value={selectedCompetitionId || ''}
            onChange={handleSelect}
            style={{ width: '100%', padding: '10px 14px', fontSize: '0.95rem', border: '2px solid var(--border)', borderRadius: 'var(--radius-sm)', minHeight: 44, outline: 'none' }}
          >
            <option value="">-- 请选择比赛 --</option>
            {competitions.map(c => (
              <option key={c.id} value={c.id}>
                {c.competition_name} ({c.competition_date}) {c.pool_length}m池{c.race_distance}m
              </option>
            ))}
            <option value="__new__">+ 新建比赛...</option>
          </select>
        </div>
      </div>

      {showNew && (
        <div style={{ marginTop: 10, padding: 14, border: '2px solid var(--primary-light)', borderRadius: 'var(--radius-sm)', background: 'var(--bg)' }}>
          <div className="form-row">
            <div className="form-group">
              <label>比赛名称 *</label>
              <input value={form.competition_name} onChange={e => setForm({ ...form, competition_name: e.target.value })} placeholder="如：2026年省运会" />
            </div>
            <div className="form-group">
              <label>比赛日期 *</label>
              <input type="date" value={form.competition_date} onChange={e => setForm({ ...form, competition_date: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>比赛地点 *</label>
              <input value={form.competition_location} onChange={e => setForm({ ...form, competition_location: e.target.value })} placeholder="如：省游泳中心" />
            </div>
            <div className="form-group">
              <label>泳池长度</label>
              <select value={form.pool_length} onChange={e => setForm({ ...form, pool_length: Number(e.target.value) })}>
                <option value={50}>50米</option>
                <option value={25}>25米</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>比赛距离</label>
              <select value={form.race_distance} onChange={e => setForm({ ...form, race_distance: Number(e.target.value) })}>
                <option value={100}>100米</option>
                <option value={50}>50米</option>
              </select>
            </div>
            <div className="form-group">
              <label>泳姿</label>
              <select value={form.stroke_type} onChange={e => setForm({ ...form, stroke_type: e.target.value })}>
                <option value="自由泳">自由泳</option>
              </select>
            </div>
          </div>
          <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
            <button className="btn btn-success" onClick={handleCreate} disabled={loading}>
              {loading ? '创建中...' : '创建比赛'}
            </button>
            <button className="btn btn-outline" onClick={() => setShowNew(false)}>取消</button>
          </div>
        </div>
      )}

      {error && <p style={{ color: 'var(--danger)', margin: '6px 0 0', fontSize: '0.82rem' }}>{error}</p>}
    </div>
  )
}
