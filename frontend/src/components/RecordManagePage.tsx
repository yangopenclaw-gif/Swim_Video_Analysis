import React, { useState, useEffect } from 'react'
import { PasswordModal } from './PasswordModal'
import { ManualEntryForm } from './ManualEntryForm'

const API_BASE = '/api'

const METRIC_LABELS: Record<string, string> = {
  reaction_time: '反应时间',
  time_50m: '50米用时',
  time_100m: '100米用时',
  dive_distance_first: '前50米潜水距离',
  stroke_count_first: '前50米划水次数',
  kick_count_first: '前50米打腿次数',
  breath_count_first: '前50米换气次数',
  turn_exit_distance: '转身出水距离',
  turn_exit_time: '转身出水用时',
  dive_distance_second: '后50米潜水距离',
  stroke_count_second: '后50米划水次数',
  kick_count_second: '后50米打腿次数',
  breath_count_second: '后50米换气次数',
}

const METRIC_GROUPS = [
  { label: '整体', keys: ['reaction_time', 'time_50m', 'time_100m'], color: '#2563eb' },
  { label: '前50米', keys: ['dive_distance_first', 'stroke_count_first', 'kick_count_first', 'breath_count_first'], color: '#0891b2' },
  { label: '转身阶段', keys: ['turn_exit_distance', 'turn_exit_time'], color: '#7c3aed' },
  { label: '后50米', keys: ['dive_distance_second', 'stroke_count_second', 'kick_count_second', 'breath_count_second'], color: '#059669' },
]

const METRIC_UNITS: Record<string, string> = {
  reaction_time: 's', time_50m: 's', time_100m: 's',
  dive_distance_first: 'm', stroke_count_first: '次', kick_count_first: '次', breath_count_first: '次',
  turn_exit_distance: 'm', turn_exit_time: 's',
  dive_distance_second: 'm', stroke_count_second: '次', kick_count_second: '次', breath_count_second: '次',
}

interface ManualRecord {
  id: string
  swimmer_name: string
  pool_length: number
  race_distance: number
  stroke_type: string
  video_id: string | null
  competition_id: string | null
  metrics: Record<string, any>
  competition_name: string | null
  race_name: string | null
  race_date: string | null
  race_location: string | null
  archived: number
  version: number
  created_at: string | null
  updated_at: string | null
  source_stats: { manual_count: number; video_marker_count: number; empty_count: number }
}

export const RecordManagePage: React.FC = () => {
  const [records, setRecords] = useState<ManualRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [editingRecord, setEditingRecord] = useState<any>(null)
  const [passwordModal, setPasswordModal] = useState<{ open: boolean; recordId: string; action: 'edit' | 'delete' | 'archive' }>({ open: false, recordId: '', action: 'edit' })
  const [passwordError, setPasswordError] = useState('')
  const [compareIds, setCompareIds] = useState<string[]>([])
  const [compareResult, setCompareResult] = useState<any>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [videos, setVideos] = useState<any[]>([])
  const [linkingRecordId, setLinkingRecordId] = useState<string | null>(null)
  const [selectedVideoId, setSelectedVideoId] = useState('')
  const [editLogs, setEditLogs] = useState<{ recordId: string; logs: any[] } | null>(null)

  useEffect(() => { fetchRecords() }, [])

  const fetchVideos = async () => {
    try {
      const res = await fetch(`${API_BASE}/videos`)
      if (res.ok) setVideos(await res.json())
    } catch {}
  }

  const fetchRecords = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/manual-records`)
      if (res.ok) setRecords(await res.json())
    } catch {} finally { setLoading(false) }
  }

  const handleEdit = (record: ManualRecord) => {
    if (record.archived === 1) {
      setPasswordModal({ open: true, recordId: record.id, action: 'edit' })
      return
    }
    setEditingRecord(record)
  }

  const handleDelete = async (record: ManualRecord) => {
    if (record.archived === 1) {
      setPasswordModal({ open: true, recordId: record.id, action: 'delete' })
      return
    }
    if (!confirm('确认删除此记录？')) return
    try {
      const res = await fetch(`${API_BASE}/manual-records/${record.id}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (res.ok) fetchRecords()
    } catch {}
  }

  const handleArchive = async (record: ManualRecord) => {
    if (record.archived === 1) return
    try {
      const res = await fetch(`${API_BASE}/manual-records/${record.id}/archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (res.ok) fetchRecords()
    } catch {}
  }

  const handlePasswordConfirm = async (password: string) => {
    setPasswordError('')
    const record = records.find(r => r.id === passwordModal.recordId)
    if (!record) return

    if (passwordModal.action === 'edit') {
      setPasswordModal({ ...passwordModal, open: false })
      setEditingRecord({ ...record, _password: password })
    } else if (passwordModal.action === 'delete') {
      try {
        const res = await fetch(`${API_BASE}/manual-records/${record.id}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password }),
        })
        if (res.ok) { setPasswordModal({ ...passwordModal, open: false }); fetchRecords() }
        else if (res.status === 403) setPasswordError('密码错误')
      } catch {}
    }
  }

  const handleCompare = async () => {
    if (compareIds.length !== 2) return
    try {
      const res = await fetch(`${API_BASE}/manual-records/compare?id1=${compareIds[0]}&id2=${compareIds[1]}`)
      if (res.ok) setCompareResult(await res.json())
    } catch {}
  }

  const toggleCompare = (id: string) => {
    setCompareIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      if (prev.length >= 2) return [prev[1], id]
      return [...prev, id]
    })
    setCompareResult(null)
  }

  const getMetricValue = (metrics: Record<string, any>, key: string) => {
    const v = metrics[key]
    if (v === undefined || v === null || v === '') return null
    if (typeof v === 'object' && v.value !== undefined) return v.value
    return v
  }

  const getMetricSource = (metrics: Record<string, any>, key: string) => {
    const v = metrics[key]
    if (typeof v === 'object' && v.source) return v.source
    return 'empty'
  }

  const renderExpandMetrics = (metrics: Record<string, any>) => {
    const parsed = metrics || {}
    return (
      <div className="metrics-expand">
        {METRIC_GROUPS.map(group => {
          const hasData = group.keys.some(k => getMetricValue(parsed, k) !== null)
          return (
            <div key={group.label} className="metric-group-block" style={{ borderLeftColor: group.color }}>
              <div className="metric-group-label" style={{ color: group.color }}>{group.label}</div>
              <div className="metric-items-grid">
                {group.keys.map(key => {
                  const val = getMetricValue(parsed, key)
                  const src = getMetricSource(parsed, key)
                  return (
                    <div key={key} className="metric-item">
                      <span className="metric-item-label">{METRIC_LABELS[key]}</span>
                      <span className="metric-item-value">
                        {val !== null ? val : '—'}
                        {val !== null && METRIC_UNITS[key] && <span className="metric-unit">{METRIC_UNITS[key]}</span>}
                      </span>
                      {val !== null && (
                        <span className={`source-dot source-dot-${src}`} title={src === 'manual' ? '手动输入' : src === 'video_marker_calc' ? '视频标记' : '空'} />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
        {!METRIC_GROUPS.some(g => g.keys.some(k => getMetricValue(parsed, k) !== null)) && (
          <div className="empty-metrics">暂无指标数据</div>
        )}
      </div>
    )
  }

  const handleLinkVideo = async (recordId: string, videoId: string) => {
    try {
      const res = await fetch(`${API_BASE}/manual-records/${recordId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: videoId }),
      })
      if (res.ok) { fetchRecords(); setLinkingRecordId(null); setSelectedVideoId('') }
    } catch {}
  }

  if (editingRecord) {
    return (
      <div>
        <button className="btn btn-outline" onClick={() => { setEditingRecord(null); fetchRecords() }} style={{ marginBottom: 16 }}>
          ← 返回列表
        </button>
        <ManualEntryForm editRecord={editingRecord} onSaved={() => { setEditingRecord(null); fetchRecords() }} />
      </div>
    )
  }

  const sourceLabel = (s: string) => s === 'manual' ? '手动' : s === 'video_marker_calc' ? '标记' : '空'

  return (
    <div className="record-manage-page">
      <div className="rm-header">
        <h2 className="rm-title">记录管理</h2>
        <div className="rm-compare-bar">

          {compareIds.length === 2 && (
            <button className="btn btn-primary" onClick={handleCompare} style={{ background: '#7c3aed' }}>
              对比选中
            </button>
          )}
          {compareIds.length > 0 && <span className="rm-compare-count">已选 {compareIds.length}/2</span>}
          {compareIds.length > 0 && (
            <button className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '2px 8px' }} onClick={() => { setCompareIds([]); setCompareResult(null) }}>
              取消选择
            </button>
          )}
        </div>
      </div>

      {compareResult && (
        <div className="compare-panel">
          <div className="compare-panel-header">
            <h3>对比分析</h3>
            <button className="btn btn-outline" style={{ fontSize: '0.78rem', padding: '4px 10px' }} onClick={() => setCompareResult(null)}>关闭</button>
          </div>
          <div className="compare-record-cards">
            <div className="compare-record-card">
              <div className="compare-record-name">{compareResult.record1.swimmer_name}</div>
              <div className="compare-record-meta">{compareResult.record1.pool_length}m池{compareResult.record1.race_distance}m</div>
              <div className="compare-record-meta">{compareResult.record1.competition_name || compareResult.record1.race_name || '未命名'}</div>
              {compareResult.record1.race_date && <div className="compare-record-meta">{compareResult.record1.race_date}</div>}
            </div>
            <div className="compare-vs">VS</div>
            <div className="compare-record-card">
              <div className="compare-record-name">{compareResult.record2.swimmer_name}</div>
              <div className="compare-record-meta">{compareResult.record2.pool_length}m池{compareResult.record2.race_distance}m</div>
              <div className="compare-record-meta">{compareResult.record2.competition_name || compareResult.record2.race_name || '未命名'}</div>
              {compareResult.record2.race_date && <div className="compare-record-meta">{compareResult.record2.race_date}</div>}
            </div>
          </div>
          {METRIC_GROUPS.map(group => {
            const groupItems = compareResult.comparison.filter((c: any) => group.keys.includes(c.key))
            if (groupItems.length === 0) return null
            return (
              <div key={group.label} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 600, padding: '4px 8px', background: group.color + '18', borderLeft: `3px solid ${group.color}`, borderRadius: '0 4px 4px 0', marginBottom: 4, color: group.color }}>
                  {group.label}
                </div>
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>指标</th>
                      <th>记录1</th>
                      <th>来源</th>
                      <th>记录2</th>
                      <th>来源</th>
                      <th>差异</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupItems.map((c: any) => {
                      const isHighDiff = c.diff_pct !== null && Math.abs(c.diff_pct) > 10
                      return (
                        <tr key={c.key} className={isHighDiff ? 'compare-highlight-row' : ''}>
                          <td>{METRIC_LABELS[c.key] || c.key}</td>
                          <td className="num">{c.value1 ?? '—'}</td>
                          <td><span className={`source-badge source-${c.source1}`}>{sourceLabel(c.source1)}</span></td>
                          <td className="num">{c.value2 ?? '—'}</td>
                          <td><span className={`source-badge source-${c.source2}`}>{sourceLabel(c.source2)}</span></td>
                          <td className="num" style={{ color: c.diff && c.diff !== 0 ? (c.diff > 0 ? '#ef4444' : '#10b981') : '#94a3b8', fontWeight: isHighDiff ? 700 : 400 }}>
                            {c.diff !== null ? `${c.diff > 0 ? '+' : ''}${c.diff}` : '—'}
                            {c.diff_pct !== null ? ` (${c.diff_pct > 0 ? '+' : ''}${c.diff_pct}%)` : ''}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )
          })}
        </div>
      )}

      {loading ? (
        <div className="rm-loading">加载中...</div>
      ) : records.length === 0 ? (
        <div className="rm-empty">暂无记录，请先在"手动录入"中添加</div>
      ) : (
        <div className="rm-list">
          {records.map(r => {
            const isExpanded = expandedId === r.id
            const isSelected = compareIds.includes(r.id)
            return (
              <div key={r.id} className={`rm-card ${isSelected ? 'rm-card-selected' : ''} ${r.archived ? 'rm-card-archived' : ''}`}>
                <div className="rm-card-main">
                  <div className="rm-card-left">
                    <input
                      type="checkbox"
                      className="rm-checkbox"
                      checked={isSelected}
                      onChange={() => toggleCompare(r.id)}
                    />
                    <div className="rm-card-info">
                      <div className="rm-card-row1">
                        <span className="rm-swimmer">{r.swimmer_name}</span>
                        <span className="rm-type">{r.pool_length}m池{r.race_distance}m</span>
                        {r.archived ? <span className="rm-badge rm-badge-archived">已归档</span> : <span className="rm-badge rm-badge-active">未归档</span>}
                      </div>
                      <div className="rm-card-row2">
                        <span>{r.competition_name || r.race_name || '未关联比赛'}</span>
                        <span className="rm-sep">·</span>
                        <span>{r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}</span>
                        <span className="rm-sep">·</span>
                        <span className="rm-source-stats">
                          <span className="rm-stat-manual">手动{r.source_stats?.manual_count || 0}</span>
                          <span className="rm-stat-sep">/</span>
                          <span className="rm-stat-marker">标记{r.source_stats?.video_marker_count || 0}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="rm-card-actions">
                    <button className="rm-action-btn rm-action-expand" onClick={() => setExpandedId(isExpanded ? null : r.id)}>
                      {isExpanded ? '收起' : '展开'}
                    </button>
                    <button className="rm-action-btn rm-action-edit" onClick={() => handleEdit(r)}>编辑</button>
                    {!r.archived && (
                      <button className="rm-action-btn rm-action-archive" onClick={() => handleArchive(r)}>归档</button>
                    )}
                    <button className="rm-action-btn rm-action-delete" onClick={() => handleDelete(r)}>删除</button>
                    <button className="rm-action-btn" style={{ color: '#6366f1' }} onClick={async () => {
                      try {
                        const res = await fetch(`${API_BASE}/manual-records/${r.id}/edit-logs`)
                        if (res.ok) {
                          const logs = await res.json()
                          setEditLogs(logs.length ? { recordId: r.id, logs } : null)
                          if (!logs.length) alert('暂无修改历史')
                        }
                      } catch {}
                    }}>历史</button>
                  </div>
                </div>
                {isExpanded && renderExpandMetrics(r.metrics)}
                {isExpanded && (
                  <div style={{ padding: '8px 16px 12px', borderTop: '1px solid var(--border)', background: '#fafbfc' }}>
                    {r.video_id ? (
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        已关联视频: {videos.find(v => v.id === r.video_id)?.display_name || r.video_id}
                      </div>
                    ) : linkingRecordId === r.id ? (
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                        <select value={selectedVideoId} onChange={e => setSelectedVideoId(e.target.value)} style={{ flex: 1, padding: '4px 8px', fontSize: '0.8rem', border: '1px solid var(--border)', borderRadius: 4, minHeight: 32 }}>
                          <option value="">选择视频</option>
                          {videos.map(v => <option key={v.id} value={v.id}>{v.display_name || v.file_name}</option>)}
                        </select>
                        <button className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '3px 8px' }} onClick={() => handleLinkVideo(r.id, selectedVideoId)} disabled={!selectedVideoId}>关联</button>
                        <button className="btn btn-outline" style={{ fontSize: '0.75rem', padding: '3px 8px' }} onClick={() => { setLinkingRecordId(null); setSelectedVideoId('') }}>取消</button>
                      </div>
                    ) : (
                      <button className="btn btn-outline" style={{ fontSize: '0.75rem', padding: '3px 8px' }} onClick={() => { setLinkingRecordId(r.id); fetchVideos() }}>
                        关联视频
                      </button>
                    )}
                  </div>
                )}
                {editLogs && editLogs.recordId === r.id && (
                  <div style={{ padding: '8px 16px 12px', borderTop: '1px solid var(--border)', background: '#f8fafc' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: 4 }}>修改历史</div>
                    {editLogs.logs.map((log: any, i: number) => (
                      <div key={i} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', padding: '2px 0', borderBottom: '1px solid #f1f5f9' }}>
                        <span style={{ color: '#6366f1' }}>{log.field_name}</span>: {log.old_value ?? '空'} → {log.new_value ?? '空'}
                        <span style={{ marginLeft: 8, fontSize: '0.68rem' }}>{log.modified_at ? new Date(log.modified_at).toLocaleString() : ''}</span>
                      </div>
                    ))}
                    <button style={{ fontSize: '0.7rem', color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', marginTop: 4 }} onClick={() => setEditLogs(null)}>关闭</button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <PasswordModal
        open={passwordModal.open}
        onConfirm={handlePasswordConfirm}
        onCancel={() => { setPasswordModal({ ...passwordModal, open: false }); setPasswordError('') }}
        error={passwordError}
      />
    </div>
  )
}
