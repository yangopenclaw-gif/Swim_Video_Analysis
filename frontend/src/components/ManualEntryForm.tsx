import React, { useState, useEffect, useRef, useCallback } from 'react'
import { AthleteSelector } from './AthleteSelector'
import { CompetitionSelector } from './CompetitionSelector'
import { VideoPlayer } from './VideoPlayer'

const API_BASE = '/api'
const DRAFT_KEY = 'manual_entry_draft'
const AUTO_SAVE_INTERVAL = 60000

interface MetricValue {
  value: string
  source: 'manual' | 'video_marker_calc' | 'empty'
}

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

interface EntryGroup {
  name: string
  required: boolean
  collapsible: boolean
  items: { label: string; key: string; unit?: string; placeholder?: string; hideOn50m?: boolean }[]
}

const ENTRY_GROUPS: EntryGroup[] = [
  {
    name: '整体',
    required: true,
    collapsible: false,
    items: [
      { label: '反应时间', key: 'reaction_time', unit: '秒', placeholder: '0.10-3.00' },
      { label: '50米用时', key: 'time_50m', unit: '秒', placeholder: '如 28.35 或 0:28.35' },
      { label: '100米用时', key: 'time_100m', unit: '秒', placeholder: '如 58.35 或 1:28.35', hideOn50m: true },
    ],
  },
  {
    name: '前50米',
    required: false,
    collapsible: true,
    items: [
      { label: '潜水距离', key: 'dive_distance_first', unit: '米', placeholder: '0-30' },
      { label: '划水次数', key: 'stroke_count_first', unit: '次', placeholder: '0-100' },
      { label: '打腿次数', key: 'kick_count_first', unit: '次', placeholder: '0-200' },
      { label: '换气次数', key: 'breath_count_first', unit: '次', placeholder: '0-80' },
    ],
  },
  {
    name: '转身阶段',
    required: false,
    collapsible: true,
    items: [
      { label: '转身出水距离', key: 'turn_surface_distance', unit: '米', placeholder: '0-30' },
      { label: '转身出水用时', key: 'turn_surface_time', unit: '秒', placeholder: '0-10' },
    ],
  },
  {
    name: '后50米',
    required: false,
    collapsible: true,
    items: [
      { label: '潜水距离', key: 'dive_distance_second', unit: '米', placeholder: '0-30' },
      { label: '划水次数', key: 'stroke_count_second', unit: '次', placeholder: '0-100' },
      { label: '打腿次数', key: 'kick_count_second', unit: '次', placeholder: '0-200' },
      { label: '换气次数', key: 'breath_count_second', unit: '次', placeholder: '0-80' },
    ],
  },
]

const SOURCE_LABELS: Record<string, string> = {
  manual: '手动',
  video_marker_calc: '标记',
  empty: '—',
}

const SOURCE_CSS: Record<string, string> = {
  manual: 'source-manual',
  video_marker_calc: 'source-video',
  empty: 'source-empty',
}

interface ManualEntryFormProps {
  editRecord?: any
  onSaved?: () => void
  linkedVideoId?: string | null
  linkedAthleteId?: string | null
}

export const ManualEntryForm: React.FC<ManualEntryFormProps> = ({ editRecord, onSaved, linkedVideoId, linkedAthleteId }) => {
  const [selectedAthlete, setSelectedAthlete] = useState<Athlete | null>(null)
  const [selectedCompetition, setSelectedCompetition] = useState<Competition | null>(null)
  const [metrics, setMetrics] = useState<Record<string, MetricValue>>({})
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [lastDraftSave, setLastDraftSave] = useState<string | null>(null)
  const autoSaveRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [showVideoPlayer, setShowVideoPlayer] = useState(false)
  const [linkedVideo, setLinkedVideo] = useState<{ id: string; display_name: string; file_name: string; athlete_name?: string; athlete_id?: string } | null>(null)
  const [availableVideos, setAvailableVideos] = useState<any[]>([])
  const [showVideoSelect, setShowVideoSelect] = useState(false)

  const poolLength = selectedCompetition?.pool_length || 50
  const raceDistance = selectedCompetition?.race_distance || 100
  const is50m = raceDistance === 50

  useEffect(() => {
    if (is50m) {
      setCollapsed({ '前50米': true, '转身阶段': true, '后50米': true })
    } else {
      setCollapsed({})
    }
  }, [is50m])

  useEffect(() => {
    if (editRecord) {
      setSelectedAthlete({ id: '', name: editRecord.swimmer_name, created_at: null })
      if (editRecord.competition_id) {
        setSelectedCompetition({
          id: editRecord.competition_id,
          competition_name: editRecord.race_name || '',
          competition_date: editRecord.race_date || '',
          competition_location: editRecord.race_location || '',
          pool_length: editRecord.pool_length,
          race_distance: editRecord.race_distance,
          stroke_type: editRecord.stroke_type,
          created_at: null,
        })
      }
      if (editRecord.metrics) {
        const loaded: Record<string, MetricValue> = {}
        for (const [k, v] of Object.entries(editRecord.metrics)) {
          if (typeof v === 'object' && v !== null && 'value' in (v as any)) {
            loaded[k] = v as MetricValue
          }
        }
        setMetrics(loaded)
      }
    }
  }, [editRecord])

  const saveDraft = useCallback(() => {
    const draft = {
      athleteId: selectedAthlete?.id,
      athleteName: selectedAthlete?.name,
      competitionId: selectedCompetition?.id,
      metrics,
      poolLength,
      raceDistance,
    }
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
    setLastDraftSave(new Date().toLocaleTimeString())
  }, [selectedAthlete, selectedCompetition, metrics, poolLength, raceDistance])

  const loadDraft = useCallback(() => {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return
    try {
      const draft = JSON.parse(raw)
      if (draft.athleteName) {
        setSelectedAthlete({ id: draft.athleteId || '', name: draft.athleteName, created_at: null })
      }
      if (draft.competitionId) {
        setSelectedCompetition(null)
      }
      if (draft.metrics) setMetrics(draft.metrics)
    } catch {}
  }, [])

  const clearDraft = useCallback(() => {
    localStorage.removeItem(DRAFT_KEY)
    setLastDraftSave(null)
  }, [])

  useEffect(() => {
    if (!editRecord) loadDraft()
  }, [])

  useEffect(() => {
    autoSaveRef.current = setInterval(saveDraft, AUTO_SAVE_INTERVAL)
    return () => { if (autoSaveRef.current) clearInterval(autoSaveRef.current) }
  }, [saveDraft])

  useEffect(() => {
    if (linkedVideoId) {
      fetch(`${API_BASE}/videos`).then(r => r.json()).then(data => {
        const videos = data.videos || data
        const v = videos.find((x: any) => x.id === linkedVideoId)
        if (v) {
          setLinkedVideo({ id: v.id, display_name: v.display_name, file_name: v.file_name, athlete_name: v.athlete_name, athlete_id: v.athlete_id })
          setShowVideoPlayer(true)
        }
      }).catch(() => {})
    }
  }, [linkedVideoId])

  const handleDerivedMetrics = useCallback((derived: Record<string, number>) => {
    setMetrics(prev => {
      const updated = { ...prev }
      for (const [key, val] of Object.entries(derived)) {
        if (updated[key]?.source === 'manual') continue
        updated[key] = { value: String(val), source: 'video_marker_calc' }
      }
      return updated
    })
  }, [])

  const handleMetricChange = (key: string, value: string) => {
    setMetrics(prev => ({
      ...prev,
      [key]: {
        value,
        source: prev[key]?.source === 'video_marker_calc' && value !== prev[key]?.value
          ? 'manual'
          : (prev[key]?.source || (value ? 'manual' : 'empty')),
      },
    }))
  }

  const toggleCollapse = (name: string) => {
    setCollapsed(prev => ({ ...prev, [name]: !prev[name] }))
  }

  const handleSave = async () => {
    setError('')
    setSuccess('')

    if (!selectedAthlete?.name) {
      setError('请选择或新建运动员')
      return
    }

    const rt = metrics.reaction_time
    if (!rt?.value || rt.value.trim() === '') {
      setError('反应时间为必填项')
      return
    }

    const payload = {
      swimmer_name: selectedAthlete.name,
      pool_length: poolLength,
      race_distance: raceDistance,
      stroke_type: selectedCompetition?.stroke_type || '自由泳',
      competition_id: selectedCompetition?.id || null,
      video_id: editRecord?.video_id || null,
      metrics,
      race_name: selectedCompetition?.competition_name || null,
      race_date: selectedCompetition?.competition_date || null,
      race_location: selectedCompetition?.competition_location || null,
    }

    setSaving(true)
    try {
      let res: Response
      if (editRecord?.id) {
        res = await fetch(`${API_BASE}/manual-records/${editRecord.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ updates: payload, version: editRecord.version }),
        })
      } else {
        res = await fetch(`${API_BASE}/manual-records`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      }
      if (res.ok) {
        setSuccess(editRecord ? '记录已更新' : '记录已保存')
        clearDraft()
        if (onSaved) onSaved()
      } else {
        const data = await res.json().catch(() => ({}))
        if (res.status === 405) {
          setError('请求被拒绝(405) - 请重启后端服务器！')
        } else if (res.status === 409) {
          setError('记录已被他人修改，请刷新后重新编辑')
        } else {
          setError(data.detail || `保存失败(${res.status})`)
        }
      }
    } catch {
      setError('网络错误，数据已暂存为草稿')
      saveDraft()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="container" style={{ paddingTop: 8 }}>
      <h2 style={{ marginBottom: 16, fontSize: '1.2rem', fontWeight: 700 }}>
        {editRecord ? '编辑记录' : '手动录入'}
      </h2>

      <AthleteSelector
        selectedAthleteId={selectedAthlete?.id || null}
        onSelect={setSelectedAthlete}
      />

      <CompetitionSelector
        selectedCompetitionId={selectedCompetition?.id || null}
        onSelect={setSelectedCompetition}
      />

      <div style={{ marginBottom: 16, padding: '10px 14px', background: 'var(--primary-light)', borderRadius: 'var(--radius-sm)', fontSize: '0.88rem' }}>
        <span style={{ fontWeight: 600 }}>比赛类型：</span>
        {poolLength}米池 {raceDistance}米 {selectedCompetition?.stroke_type || '自由泳'}
        {is50m && <span style={{ color: 'var(--text-secondary)', marginLeft: 8, fontSize: '0.8rem' }}>(50米比赛：可选分组默认折叠)</span>}
      </div>

      {ENTRY_GROUPS.map(group => {
        const isGroupCollapsed = collapsed[group.name] || false
        const visibleItems = group.items.filter(item => {
          if ((item as any).hideOn50m && is50m) return false
          return true
        })
        if (visibleItems.length === 0) return null

        return (
          <div
            key={group.name}
            className={`entry-group ${isGroupCollapsed ? 'collapsed' : ''}`}
          >
            <div
              className="entry-group-title"
              onClick={() => group.collapsible && toggleCollapse(group.name)}
            >
              <span>{group.name}</span>
              {group.required ? (
                <span className="required-mark">*必选</span>
              ) : (
                <span className="optional-mark">可选</span>
              )}
              {is50m && !group.required && (
                <span style={{ fontSize: '0.7rem', color: 'var(--warning)', marginLeft: 4 }}>
                  100米适用
                </span>
              )}
              {group.collapsible && (
                <span className="collapse-icon">
                  {isGroupCollapsed ? '▶' : '▼'}
                </span>
              )}
            </div>
            <div className="entry-group-body">
              <div className="entry-form-grid">
                {visibleItems.map(item => {
                  const mv = metrics[item.key] || { value: '', source: 'empty' as const }
                  return (
                    <div key={item.key} className="metric-row">
                      <label>{item.label}</label>
                      <input
                        type="text"
                        value={mv.value}
                        onChange={e => handleMetricChange(item.key, e.target.value)}
                        placeholder={item.placeholder || '—'}
                      />
                      {item.unit && <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', minWidth: 16 }}>{item.unit}</span>}
                      <span className={`source-badge ${SOURCE_CSS[mv.source] || SOURCE_CSS.empty}`}>
                        {SOURCE_LABELS[mv.source] || '—'}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )
      })}

      {showVideoPlayer && linkedVideo ? (
        <div style={{ marginTop: 16 }}>
          <VideoPlayer
            videoId={linkedVideo.id}
            fileName={linkedVideo.display_name || linkedVideo.file_name}
            athleteName={linkedVideo.athlete_name}
            athleteId={linkedVideo.athlete_id || linkedAthleteId || undefined}
            onBack={() => setShowVideoPlayer(false)}
            onDerivedMetrics={handleDerivedMetrics}
            showGuide={true}
          />
        </div>
      ) : (
        <div style={{ marginTop: 12, marginBottom: 8 }}>
          <button
            className="btn btn-outline"
            style={{ fontSize: '0.82rem', padding: '4px 14px' }}
            onClick={async () => {
              try {
                const res = await fetch(`${API_BASE}/videos`)
                const data = await res.json()
                const videos = Array.isArray(data) ? data : (data.videos || [])
                if (!videos.length) { alert('暂无视频，请先上传'); return }
                setAvailableVideos(videos)
                setShowVideoSelect(true)
              } catch { alert('获取视频列表失败') }
            }}
          >
            🎬 关联视频
          </button>
          {linkedVideo && !showVideoPlayer && (
            <span style={{ marginLeft: 8, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              已关联: {linkedVideo.display_name || linkedVideo.file_name}
              <button style={{ marginLeft: 4, fontSize: '0.75rem', color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setShowVideoPlayer(true)}>打开</button>
            </span>
          )}
          {showVideoSelect && availableVideos.length > 0 && (
            <div style={{ marginTop: 8, padding: 10, background: '#f8fafc', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 6 }}>选择视频</div>
              <select
                style={{ width: '100%', padding: '6px 10px', fontSize: '0.82rem', border: '1px solid var(--border)', borderRadius: 4, marginBottom: 8 }}
                onChange={e => {
                  const v = availableVideos.find((x: any) => x.id === e.target.value)
                  if (v) {
                    setLinkedVideo({ id: v.id, display_name: v.display_name, file_name: v.file_name, athlete_name: v.athlete_name, athlete_id: v.athlete_id })
                    setShowVideoSelect(false)
                    setShowVideoPlayer(true)
                  }
                }}
                defaultValue=""
              >
                <option value="" disabled>请选择视频</option>
                {availableVideos.map((v: any) => (
                  <option key={v.id} value={v.id}>{v.display_name || v.file_name}{v.athlete_name ? ` - ${v.athlete_name}` : ''}</option>
                ))}
              </select>
              <button className="btn btn-outline" style={{ fontSize: '0.75rem', padding: '2px 8px' }} onClick={() => setShowVideoSelect(false)}>取消</button>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 16, flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存'}
        </button>
        <button className="btn btn-outline" onClick={saveDraft}>
          暂存草稿
        </button>
        {lastDraftSave && <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>草稿已保存于 {lastDraftSave}</span>}
      </div>

      {error && <p style={{ color: 'var(--danger)', marginTop: 8, fontSize: '0.88rem' }}>{error}</p>}
      {success && <p style={{ color: 'var(--success)', marginTop: 8, fontSize: '0.88rem' }}>{success}</p>}
    </div>
  )
}
