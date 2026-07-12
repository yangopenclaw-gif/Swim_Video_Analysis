import React, { useState, useEffect, useRef, useCallback } from 'react'
import Cropper from 'react-easy-crop'
import { VideoUploader } from './uploader'
import { VideoManager, UploadStatusBar } from './VideoManager'

const API_BASE = '/api'

const OPTIONS_100M: string[] = [
  '起跳反应时间', '出发后潜水时间', '出发后潜水距离', '水下腿次数',
  '前程途中游速度', '前程总划水次数', '前程水面交替打腿次数', '前程总呼吸次数',
  '半程触壁转身时刻', '前程整体用时', '转身后出水用时', '转身出水距离',
  '转身水下腿次数', '后程途中游速度', '后程总划水次数', '后程水面交替打腿次数',
  '后程总呼吸次数', '触壁终点用时',
]

const OPTIONS_50M_50POOL: string[] = [
  '起跳反应时间', '出发后潜水时间', '出发后潜水距离', '水下腿次数',
  '途中游速度', '途中游划水次数', '水面交替打腿次数', '总呼吸次数', '触壁终点用时',
]

const OPTIONS_50M_25POOL: string[] = OPTIONS_100M

interface AnalysisResult { [key: string]: any }

interface Record {
  id: string
  swimmer_name: string
  pool_length: number
  race_distance: number
  stroke_type: string
  analysis_result: AnalysisResult
  race_name: string | null
  race_date: string | null
  race_location: string | null
  archive_time: string | null
  created_at: string | null
  linked_video_id?: string | null
}

type PageType = 'home' | 'records' | 'record-detail' | 'video' | 'compare' | 'entry'
type UploadPhase = 'idle' | 'uploading' | 'uploaded' | 'analyzing' | 'completed' | 'failed'

const parseHash = (): { page: PageType; swimmer?: string; subPage?: string; videoId?: string } => {
  const h = window.location.hash.slice(1)
  const parts = h.split('/').filter(Boolean)
  if (parts.length === 0) return { page: 'home' }
  const p0 = parts[0]
  if (p0 === 'records') {
    if (parts.length >= 2) return { page: 'record-detail', swimmer: decodeURIComponent(parts[1]), subPage: parts[2] || 'list' }
    return { page: 'records' }
  }
  if (p0 === 'video') return { page: 'video', videoId: parts[1] }
  if (p0 === 'entry') return { page: 'entry' }
  if (p0 === 'compare') return { page: 'compare' }
  return { page: 'home' }
}

const navigateTo = (page: PageType, extra?: { swimmer?: string; subPage?: string; videoId?: string }) => {
  let hash = ''
  if (page === 'records') hash = '#/records'
  else if (page === 'record-detail') hash = `#/records/${encodeURIComponent(extra?.swimmer || '')}${extra?.subPage ? '/' + extra.subPage : ''}`
  else if (page === 'video') hash = `#/video${extra?.videoId ? '/' + extra.videoId : ''}`
  else if (page === 'entry') hash = '#/entry'
  else if (page === 'compare') hash = '#/compare'
  else hash = '#/'
  window.location.hash = hash
}

function App() {
  const [page, setPageInternal] = useState<PageType>(parseHash().page)
  const [selectedSwimmer, setSelectedSwimmer] = useState('杨钧涵')
  const [swimmerName, setSwimmerName] = useState('杨钧涵')
  const [poolLength, setPoolLength] = useState(50)
  const [raceDistance, setRaceDistance] = useState(100)
  const [swimmerPosition, setSwimmerPosition] = useState(1)
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>('idle')
  const [selectedOptions, setSelectedOptions] = useState<string[]>([])
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)
  const [records, setRecords] = useState<Record[]>([])
  const [showArchiveModal, setShowArchiveModal] = useState(false)
  const [archiveForm, setArchiveForm] = useState({ race_name: '', race_date: '', race_location: '' })
  const [compareId1, setCompareId1] = useState('')
  const [compareId2, setCompareId2] = useState('')
  const [compareData, setCompareData] = useState<any>(null)
  const [allRecords, setAllRecords] = useState<Record[]>([])
  const [analyzeProgress, setAnalyzeProgress] = useState(0)
  const [analyzeMessage, setAnalyzeMessage] = useState('')

  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadUploadedChunks, setUploadUploadedChunks] = useState(0)
  const [uploadTotalChunks, setUploadTotalChunks] = useState(0)
  const [uploadSpeed, setUploadSpeed] = useState(0)
  const [uploadEta, setUploadEta] = useState(0)
  const [uploadStatusText, setUploadStatusText] = useState('')

  const [videoList, setVideoList] = useState<any[]>([])

  const fileInputRef = useRef<HTMLInputElement>(null)
  const uploaderRef = useRef<VideoUploader | null>(null)
  const analyzeIntervalRef = useRef<number | null>(null)
  const uploadStartTimeRef = useRef<number>(Date.now())

  const [pendingUploads, setPendingUploads] = useState<any[]>([])
  const [showVideoManager, setShowVideoManager] = useState(false)
  const [analyzeVideoId, setAnalyzeVideoId] = useState<string | null>(null)
  const [analyzeVideoForm, setAnalyzeVideoForm] = useState({
    swimmer_name: '杨钧涵',
    pool_length: 50,
    race_distance: 100,
    swimmer_position: 1,
  })
  const [analyzeVideoOptions, setAnalyzeVideoOptions] = useState<string[]>([])
  const [analyzeVideoStep, setAnalyzeVideoStep] = useState<'params' | 'options'>('params')
  const [editingRecord, setEditingRecord] = useState<Record | null>(null)
  const [editPassword, setEditPassword] = useState('')
  const [editError, setEditError] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'record' | 'video'; id: string; password: string; error: string } | null>(null)
  const [swimmerProfile, setSwimmerProfile] = useState<{ birth_date: string | null } | null>(null)
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set())
  const [expandedComps, setExpandedComps] = useState<Set<string>>(new Set())
  const [recordSubPage, setRecordSubPage] = useState<'list' | 'detail' | 'result'>('list')
  const [selectedComp, setSelectedComp] = useState<{ name: string; date: string | null; location: string | null; records: Record[] } | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<Record | null>(null)
  const [liked, setLiked] = useState(false)
  const [popularity, setPopularity] = useState(0)
  const [collapsedYears, setCollapsedYears] = useState<Set<string>>(new Set())
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [swimmerAvatars, setSwimmerAvatars] = useState<Record<string, string>>({})
  const [cropModal, setCropModal] = useState<{ imageUrl: string; name: string } | null>(null)
  const [cropArea, setCropArea] = useState<{ x: number; y: number; width: number; height: number } | null>(null)
  const [cropPos, setCropPos] = useState({ x: 0, y: 0 })
  const [cropZoom, setCropZoom] = useState(1)

  const setPage = (p: PageType, extra?: { swimmer?: string; subPage?: string; videoId?: string }) => {
    navigateTo(p, extra)
  }

  useEffect(() => {
    const handler = () => {
      const { page: p, swimmer, subPage, videoId } = parseHash()
      setPageInternal(p)
      if (p === 'record-detail' && swimmer) {
        setSelectedSwimmer(swimmer)
        setSwimmerName(swimmer)
        setRecordSubPage((subPage as any) || 'list')
      }
      if (p === 'video' && videoId) {
        const evt = new CustomEvent('playVideo', { detail: videoId })
        window.dispatchEvent(evt)
      }
    }
    window.addEventListener('hashchange', handler)
    handler()
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  useEffect(() => {
    const pending = VideoUploader.getPendingUploads()
    if (pending.length > 0) {
      setPendingUploads(pending)
    }
    allSwimmerNames().forEach(name => {
      fetch(`${API_BASE}/swimmer_profile/${encodeURIComponent(name)}`).then(r => r.ok ? r.json() : null).then(d => {
        if (d?.avatar_url) setSwimmerAvatars(prev => ({ ...prev, [name]: d.avatar_url }))
      }).catch(() => {})
    })
  }, [])

  useEffect(() => {
    if (page === 'record-detail') {
      setSwimmerName(selectedSwimmer)
      setRecordSubPage('list')
      setSelectedComp(null)
      setSelectedEvent(null)
      fetchRecords(selectedSwimmer)
      fetch(`${API_BASE}/swimmer_profile/${selectedSwimmer}`).then(r => r.ok ? r.json() : null).then(d => { if (d) { setSwimmerProfile(d); setAvatarUrl(d.avatar_url || null) } }).catch(() => {})
    }
    if (page === 'compare') {
      fetchAllRecords()
    }
    if (page === 'entry') {
      fetchAllRecords()
    }
  }, [page, selectedSwimmer])

  useEffect(() => {
    if (records.length > 0 && expandedYears.size === 0) {
      const firstYear = records[0]?.race_date?.substring(0, 4) || records[0]?.archive_time?.substring(0, 4) || ''
      if (firstYear) setExpandedYears(new Set([firstYear]))
    }
  }, [records])

  useEffect(() => {
    if (raceDistance === 50 && poolLength === 50) {
      setSelectedOptions([...OPTIONS_50M_50POOL])
    } else {
      setSelectedOptions([...OPTIONS_50M_25POOL])
    }
  }, [raceDistance, poolLength])

  const fetchRecords = async (name: string) => {
    try {
      const res = await fetch(`${API_BASE}/records/${encodeURIComponent(name)}`)
      if (res.ok) setRecords(await res.json())
    } catch {}
  }

  const fetchAllRecords = async () => {
    try {
      const res = await fetch(`${API_BASE}/all_records`)
      if (res.ok) setAllRecords(await res.json())
    } catch {}
  }

  const getAvailableOptions = () => {
    if (raceDistance === 50 && poolLength === 50) return OPTIONS_50M_50POOL
    return OPTIONS_50M_25POOL
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setVideoFile(e.target.files[0])
      setUploadPhase('idle')
      setTaskId(null)
      setAnalysisResult(null)
      setUploadProgress(0)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setVideoFile(e.dataTransfer.files[0])
      setUploadPhase('idle')
    }
  }

  const handleUpload = async () => {
    if (!videoFile) return

    if (uploaderRef.current) {
      uploaderRef.current.destroy()
      uploaderRef.current = null
    }

    setUploadPhase('uploading')
    setUploadProgress(0)
    setUploadSpeed(0)
    setUploadEta(0)
    setUploadUploadedChunks(0)
    setUploadTotalChunks(0)
    setUploadStatusText('正在初始化上传...')
    uploadStartTimeRef.current = Date.now()

    const uploader = new VideoUploader({
      onProgress: (pct, uploaded, total) => {
        setUploadProgress(pct)
      },
      onSpeed: (speed) => {
        setUploadSpeed(speed)
      },
      onEta: (eta) => {
        setUploadEta(eta)
      },
      onStatus: (text) => {
        setUploadStatusText(text)
        const match = text.match(/(\d+)\/(\d+)/)
        if (match) {
          setUploadUploadedChunks(parseInt(match[1]))
          setUploadTotalChunks(parseInt(match[2]))
        }
      },
      onComplete: (taskId) => {
        setTaskId(taskId)
        setUploadPhase('uploaded')
        setUploadStatusText('上传完成')
      },
      onError: (msg) => {
        setUploadPhase('failed')
        setUploadStatusText(msg)
      },
    })

    uploaderRef.current = uploader
    await uploader.upload(videoFile, swimmerName, poolLength, raceDistance, swimmerPosition)
  }

  const handleCancelUpload = () => {
    if (uploaderRef.current) {
      uploaderRef.current.cancel()
      uploaderRef.current.destroy()
      uploaderRef.current = null
    }
    setUploadPhase('idle')
    setUploadStatusText('')
    setUploadProgress(0)
  }

  const handleResumeUpload = async (pending: any) => {
    if (uploaderRef.current) {
      uploaderRef.current.destroy()
      uploaderRef.current = null
    }

    setUploadPhase('uploading')
    setUploadProgress(0)
    setUploadSpeed(0)
    setUploadEta(0)
    setUploadUploadedChunks(0)
    setUploadTotalChunks(0)
    setUploadStatusText('请重新选择视频文件以续传...')

    const fileInput = document.createElement('input')
    fileInput.type = 'file'
    fileInput.accept = 'video/*'
    fileInput.onchange = async (e: any) => {
      const file = e.target.files?.[0]
      if (!file) {
        setUploadPhase('idle')
        return
      }

      setUploadStatusText('正在恢复上传...')

      const uploader = new VideoUploader({
        onProgress: (pct, uploaded, total) => {
          setUploadProgress(pct)
        },
        onSpeed: (speed) => {
          setUploadSpeed(speed)
        },
        onEta: (eta) => {
          setUploadEta(eta)
        },
        onStatus: (text) => {
          setUploadStatusText(text)
          const match = text.match(/(\d+)\/(\d+)/)
          if (match) {
            setUploadUploadedChunks(parseInt(match[1]))
            setUploadTotalChunks(parseInt(match[2]))
          }
        },
        onComplete: (taskId) => {
          setTaskId(taskId)
          setUploadPhase('uploaded')
          setPendingUploads(prev => prev.filter(p => p.uploadId !== pending.uploadId))
          setUploadStatusText('上传完成')
        },
        onError: (msg) => {
          setUploadPhase('failed')
          setUploadStatusText(msg)
        },
      })

      uploaderRef.current = uploader
      await uploader.upload(file, pending.swimmerName, pending.poolLength, pending.raceDistance, pending.swimmerPosition)
    }
    fileInput.click()
  }

  const handleDiscardPending = (uploadId: string) => {
    VideoUploader.removePendingUpload(uploadId)
    setPendingUploads(prev => prev.filter(p => p.uploadId !== uploadId))
  }

  const fetchVideoList = async () => {
    try {
      const res = await fetch(`${API_BASE}/videos`)
      if (res.ok) setVideoList(await res.json())
    } catch {}
  }

  const handleDeleteVideo = async (taskId: string) => {
    if (!confirm('确定删除此视频及其分析数据？此操作不可恢复。')) return
    try {
      const res = await fetch(`${API_BASE}/videos/${taskId}`, { method: 'DELETE' })
      if (res.ok) {
        fetchVideoList()
        fetchRecords(swimmerName)
        fetchAllRecords()
      }
    } catch {}
  }

  const handleAnalyzeExistingVideo = (videoId: string) => {
    setAnalyzeVideoId(videoId)
    setAnalyzeVideoForm({
      swimmer_name: swimmerName,
      pool_length: poolLength,
      race_distance: raceDistance,
      swimmer_position: 1,
    })
    setAnalyzeVideoStep('params')
    const opts = raceDistance === 50 && poolLength === 50 ? OPTIONS_50M_50POOL : OPTIONS_50M_25POOL
    setAnalyzeVideoOptions([...opts])
  }

  const handleStartAnalyzeExisting = async () => {
    if (!analyzeVideoId || analyzeVideoOptions.length === 0) return
    setTaskId(analyzeVideoId)
    setSwimmerName(analyzeVideoForm.swimmer_name)
    setPoolLength(analyzeVideoForm.pool_length)
    setRaceDistance(analyzeVideoForm.race_distance)
    setSwimmerPosition(analyzeVideoForm.swimmer_position)
    setSelectedOptions(analyzeVideoOptions)
    setAnalyzeVideoId(null)
    setUploadPhase('analyzing')
    setAnalyzeProgress(0)
    setAnalyzeMessage('正在启动分析...')
    uploadStartTimeRef.current = Date.now()
    try {
      const res = await fetch(`${API_BASE}/analyze_existing/${analyzeVideoId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          analysis_options: analyzeVideoOptions,
          swimmer_name: analyzeVideoForm.swimmer_name,
          pool_length: analyzeVideoForm.pool_length,
          race_distance: analyzeVideoForm.race_distance,
          swimmer_position: analyzeVideoForm.swimmer_position,
        }),
      })
      if (!res.ok) { setUploadPhase('failed'); return }
      const data = await res.json()
      if (data.status === 'completed') {
        setAnalysisResult(data.result)
        setUploadPhase('completed')
        return
      }
      if (data.status === 'analyzing') {
        analyzeIntervalRef.current = window.setInterval(async () => {
          try {
            const pr = await fetch(`${API_BASE}/analyze/progress/${analyzeVideoId}`)
            if (pr.ok) {
              const pd = await pr.json()
              setAnalyzeProgress(pd.progress || 0)
              setAnalyzeMessage(pd.message || '')
              if (pd.status === 'completed') {
                if (analyzeIntervalRef.current) clearInterval(analyzeIntervalRef.current)
                setAnalysisResult(pd.result)
                setUploadPhase('completed')
                fetchVideoList()
              } else if (pd.status === 'failed') {
                if (analyzeIntervalRef.current) clearInterval(analyzeIntervalRef.current)
                setUploadPhase('failed')
              }
            }
          } catch {}
        }, 1000)
      }
    } catch { setUploadPhase('failed') }
  }

  const handleAnalyze = async () => {
    if (!taskId || selectedOptions.length === 0) return
    setUploadPhase('analyzing'); setAnalyzeProgress(0); setAnalyzeMessage('正在启动分析...')
    try {
      const res = await fetch(`${API_BASE}/analyze/${taskId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(selectedOptions) })
      if (!res.ok) { setUploadPhase('failed'); return }
      const data = await res.json()
      if (data.status === 'analyzing') {
        analyzeIntervalRef.current = window.setInterval(async () => {
          try {
            const pr = await fetch(`${API_BASE}/analyze/progress/${taskId}`)
            if (pr.ok) {
              const pd = await pr.json()
              setAnalyzeProgress(pd.progress || 0); setAnalyzeMessage(pd.message || '')
              if (pd.status === 'completed') { if (analyzeIntervalRef.current) clearInterval(analyzeIntervalRef.current); setAnalysisResult(pd.result); setUploadPhase('completed') }
              else if (pd.status === 'failed') { if (analyzeIntervalRef.current) clearInterval(analyzeIntervalRef.current); setUploadPhase('failed') }
            }
          } catch {}
        }, 1000)
      } else if (data.status === 'completed') { setAnalysisResult(data.result); setUploadPhase('completed') }
    } catch { setUploadPhase('failed') }
  }

  const handleArchive = async () => {
    if (!taskId) return
    try {
      const params = new URLSearchParams(archiveForm)
      const res = await fetch(`${API_BASE}/archive/${taskId}?${params}`, { method: 'POST' })
      if (res.ok) {
        setShowArchiveModal(false)
        fetchRecords(swimmerName)
      }
    } catch {}
  }

  const handleDeleteRecord = (id: string) => {
    setDeleteConfirm({ type: 'record', id, password: '', error: '' })
  }

  const confirmDelete = async () => {
    if (!deleteConfirm) return
    if (deleteConfirm.password !== 'ycz') { setDeleteConfirm({ ...deleteConfirm, error: '密码错误' }); return }
    try {
      const res = await fetch(`${API_BASE}/records/${deleteConfirm.id}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: deleteConfirm.password }) })
      if (res.ok) { setDeleteConfirm(null); fetchRecords(swimmerName); fetchAllRecords() }
      else { const d = await res.json().catch(() => ({})); setDeleteConfirm({ ...deleteConfirm, error: d.detail || '删除失败' }) }
    } catch { setDeleteConfirm({ ...deleteConfirm, error: '网络错误' }) }
  }

  const handleCompare = async () => {
    if (!compareId1 || !compareId2) return
    try {
      const res = await fetch(`${API_BASE}/compare?id1=${compareId1}&id2=${compareId2}`)
      if (res.ok) setCompareData(await res.json())
    } catch {}
  }

  const toggleOption = (opt: string) => {
    setSelectedOptions(prev =>
      prev.includes(opt) ? prev.filter(o => o !== opt) : [...prev, opt]
    )
  }

  const selectAll = () => setSelectedOptions([...getAvailableOptions()])
  const deselectAll = () => setSelectedOptions([])

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const formatSpeed = (bytesPerSec: number) => {
    if (bytesPerSec < 1024) return bytesPerSec.toFixed(0) + ' B/s'
    if (bytesPerSec < 1024 * 1024) return (bytesPerSec / 1024).toFixed(1) + ' KB/s'
    return (bytesPerSec / (1024 * 1024)).toFixed(2) + ' MB/s'
  }

  const formatEta = (seconds: number) => {
    if (seconds <= 0 || !isFinite(seconds)) return '计算中...'
    if (seconds < 60) return `约${Math.ceil(seconds)}秒`
    const m = Math.floor(seconds / 60)
    const s = Math.ceil(seconds % 60)
    return `约${m}分${s}秒`
  }



  const formatMetricValue = (key: string, v: any): string => {
    if (typeof v !== 'number') return String(v)
    if (key.includes('用时') || key.includes('时间')) {
      if (v < 60) return `${v.toFixed(2)}秒`
      const m = Math.floor(v / 60); const s = v % 60
      return `${m}分${s.toFixed(2)}秒`
    }
    return String(Math.round(v))
  }

  const isUploading = uploadPhase === 'uploading'

  const renderUploadSection = () => (
    <div className="card">
      <div className="card-title"><span className="icon">📹</span> 上传比赛视频</div>
      <div style={{
        background: '#fff3e0',
        borderRadius: 'var(--radius-sm)',
        padding: '12px 16px',
        marginBottom: 16,
        fontSize: '0.82rem',
        color: '#e65100',
        border: '1px solid #ffe0b2',
      }}>
        <div style={{ fontWeight: 600, marginBottom: 6, fontSize: '0.85rem' }}>⚠️ 为保证分析结果准确度，视频拍摄需满足以下要求：</div>
        <ul style={{ margin: 0, paddingLeft: 16, lineHeight: 1.7, fontSize: '0.8rem' }}>
          <li>从<strong>侧面</strong>拍摄，镜头与泳道平行，能看清运动员全程侧影</li>
          <li>拍摄范围需<strong>覆盖完整泳道</strong>（出发到触壁），不可只拍半段</li>
          <li>画面中运动员<strong>不可被遮挡</strong>，身体关键部位（头、肩、手、脚）需清晰可见</li>
          <li>视频需包含<strong>出发前静止画面</strong>（至少1-2秒），以便识别起跳时刻</li>
          <li>视频需包含<strong>触壁后画面</strong>（至少1-2秒），以便识别终点时刻</li>
          <li>建议分辨率 ≥ 720p，帧率 ≥ 30fps，画面稳定不抖动</li>
          <li>多人泳道时，各运动员在画面中需<strong>有足够间距</strong>，避免重叠</li>
        </ul>
      </div>
      {pendingUploads.length > 0 && uploadPhase !== 'uploading' && (
        <div style={{
          background: '#fff8e1',
          borderRadius: 'var(--radius-sm)',
          padding: '12px 16px',
          marginBottom: 16,
          fontSize: '0.85rem',
          color: '#f57f17',
          border: '1px solid #ffe082',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>⚠️ 检测到未完成的上传</div>
          {pendingUploads.map(p => (
            <div key={p.uploadId} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #ffe082', flexWrap: 'wrap', gap: 8 }}>
              <span>{p.filename} ({formatSize(p.fileSize)}) · {p.swimmerName} · {p.poolLength}米池/{p.raceDistance}米</span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-sm btn-primary" onClick={() => handleResumeUpload(p)}>重新选择文件续传</button>
                <button className="btn btn-sm btn-outline" onClick={() => handleDiscardPending(p.uploadId)} style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>放弃</button>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="form-row">
        <div className="form-group">
          <label>运动员</label>
          <select value={swimmerName} onChange={e => setSwimmerName(e.target.value)} disabled={isUploading}>
            <option value="杨钧涵">杨钧涵</option>
            <option value="杨涴婷">杨涴婷</option>
          </select>
        </div>
        <div className="form-group">
          <label>泳池长度</label>
          <select value={poolLength} onChange={e => setPoolLength(Number(e.target.value))} disabled={isUploading}>
            <option value={25}>25米池</option>
            <option value={50}>50米池</option>
          </select>
        </div>
        <div className="form-group">
          <label>比赛距离</label>
          <select value={raceDistance} onChange={e => setRaceDistance(Number(e.target.value))} disabled={isUploading}>
            <option value={50}>50米</option>
            <option value={100}>100米</option>
          </select>
        </div>
        <div className="form-group">
          <label>泳姿</label>
          <select value="自由泳" disabled>
            <option value="自由泳">自由泳</option>
          </select>
        </div>
        <div className="form-group">
          <label>被分析者（从左往右）</label>
          <select value={swimmerPosition} onChange={e => setSwimmerPosition(Number(e.target.value))} disabled={isUploading}>
            <option value={1}>第1人（最左侧）</option>
            <option value={2}>第2人</option>
            <option value={3}>第3人</option>
            <option value={4}>第4人</option>
            <option value={5}>第5人</option>
            <option value={6}>第6人</option>
            <option value={7}>第7人</option>
            <option value={8}>第8人</option>
            <option value={9}>第9人（最右侧）</option>
          </select>
        </div>
      </div>

      <div style={{
        background: 'var(--primary-light)',
        borderRadius: 'var(--radius-sm)',
        padding: '8px 12px',
        marginBottom: 14,
        fontSize: '0.8rem',
        color: 'var(--primary-dark)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 6,
      }}>
        <span>💡</span>
        <span>视频中可能包含多名运动员，系统将自动检测所有人物并按从左到右排序。请选择您要分析的运动员是第几人（从左往右数）。</span>
      </div>

      <div
        className="upload-area"
        onClick={() => !isUploading && fileInputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={handleDrop}
        style={isUploading ? { pointerEvents: 'none', opacity: 0.6 } : {}}
      >
        <div className="upload-icon">📁</div>
        <p>点击或拖拽上传比赛视频</p>
        <p style={{ fontSize: '0.8rem', marginTop: 4 }}>支持 mp4/avi/mov/mkv/webm 格式 · 分片断点续传</p>
        {videoFile && <div className="filename">{videoFile.name} ({formatSize(videoFile.size)})</div>}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
      </div>

      {isUploading && (
        <div style={{ marginBottom: 14, marginTop: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5, fontSize: '0.85rem' }}>
            <span style={{ flex: 1, marginRight: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{uploadStatusText}</span>
            <span style={{ fontWeight: 600, color: 'var(--primary)', flexShrink: 0 }}>{uploadProgress}%</span>
          </div>
          <div style={{
            width: '100%',
            height: 12,
            background: 'var(--border)',
            borderRadius: 6,
            overflow: 'hidden',
          }}>
            <div style={{
              width: `${uploadProgress}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #1a73e8, #4fc3f7)',
              borderRadius: 6,
              transition: 'width 0.3s ease',
            }} />
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 5, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '2px 12px' }}>
            <span>分片 {uploadUploadedChunks}/{uploadTotalChunks}</span>
            <span>速度 {uploadSpeed > 0 ? formatSpeed(uploadSpeed) : '计算中...'}</span>
            {uploadEta > 0 && <span>剩余 {formatEta(uploadEta)}</span>}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button
          onClick={handleUpload}
          disabled={!videoFile || isUploading || uploadPhase === 'uploaded'}
        >
          {isUploading ? '上传中...' : uploadPhase === 'uploaded' ? '已上传' : '开始上传'}
        </button>
        {isUploading && (
          <button className="btn btn-danger" onClick={handleCancelUpload}>
            取消上传
          </button>
        )}
      </div>
    </div>
  )

  const renderAnalysisOptions = () => {
    if (uploadPhase !== 'uploaded') return null
    const options = getAvailableOptions()
    return (
      <div className="card">
        <div className="card-title"><span className="icon">🔍</span> 选择分析内容</div>
        <div className="select-all-bar">
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={selectedOptions.length === options.length} onChange={selectAll} />
            全选
          </label>
          <button className="btn btn-sm btn-outline" onClick={selectAll}>全选</button>
          <button className="btn btn-sm btn-outline" onClick={deselectAll}>取消全选</button>
          <span style={{ marginLeft: 'auto', color: 'var(--text-secondary)' }}>
            已选 {selectedOptions.length}/{options.length} 项
          </span>
        </div>
        <div className="options-grid">
          {options.map(opt => (
            <label key={opt} className="option-item">
              <input
                type="checkbox"
                checked={selectedOptions.includes(opt)}
                onChange={() => toggleOption(opt)}
              />
              {opt}
            </label>
          ))}
        </div>
        <button
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={selectedOptions.length === 0 || uploadPhase === 'analyzing'}
        >
          {uploadPhase === 'analyzing' ? '分析中...' : '即时分析'}
        </button>
      </div>
    )
  }

  const renderResult = () => {
    if (uploadPhase === 'analyzing') {
      const elapsed = (Date.now() - (uploadStartTimeRef.current || Date.now())) / 1000
      const remaining = analyzeProgress > 5 ? Math.max(0, Math.round((100 - analyzeProgress) / analyzeProgress * elapsed)) : 60
      return (
        <div className="card">
          <div className="loading">
            <div style={{ width: '100%', maxWidth: 400 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.9rem' }}>
                <span>正在分析视频...</span>
                <span style={{ fontWeight: 600, color: 'var(--primary)' }}>{analyzeProgress}%</span>
              </div>
              <div style={{ width: '100%', height: 14, background: 'var(--border)', borderRadius: 7, overflow: 'hidden' }}>
                <div style={{ width: `${analyzeProgress}%`, height: '100%', background: 'linear-gradient(90deg, #1a73e8, #4fc3f7)', borderRadius: 7, transition: 'width 0.5s ease' }} />
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 6, textAlign: 'center' }}>{analyzeMessage}</div>
              {analyzeProgress > 5 && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 3, textAlign: 'center' }}>预估剩余时间：{formatEta(remaining)}</div>}
            </div>
          </div>
        </div>
      )
    }

    if (uploadPhase === 'failed') {
      return (<div className="card"><div className="empty-state"><div className="icon">❌</div><p>操作失败，请重试</p>{uploadStatusText && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{uploadStatusText}</p>}</div></div>)
    }

    if (!analysisResult || uploadPhase !== 'completed') return null
    const entries = Object.entries(analysisResult).filter(([key]) => key !== '_meta')
    const meta = analysisResult._meta

    return (
      <div className="card">
        <div className="card-title"><span className="icon">📊</span> 分析结果</div>
        {meta && (
          <div style={{ background: '#e6f4ea', borderRadius: 'var(--radius-sm)', padding: '8px 12px', marginBottom: 10, fontSize: '0.8rem', color: '#1e7e34', display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span>🏊</span>
            <span>检测到 <strong>{meta.max_persons_detected}</strong> 人，分析第 <strong>{meta.swimmer_position}</strong> 人</span>
            {meta.race_duration != null && <span>比赛用时：<strong>{formatTime(meta.race_duration)}</strong></span>}
          </div>
        )}
        <table className="result-table">
          <thead><tr><th>分析指标</th><th>数值</th></tr></thead>
          <tbody>
            {entries.map(([key, val]) => (
              <tr key={key}><td>{key}</td><td className="value">{typeof val === 'string' ? val : JSON.stringify(val)}</td></tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: 14, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button className="btn btn-success" onClick={() => setShowArchiveModal(true)}>归档此结果</button>
        </div>
      </div>
    )
  }

  const renderArchiveModal = () => {
    if (!showArchiveModal) return null
    return (
      <div className="modal-overlay" onClick={() => setShowArchiveModal(false)}>
        <div className="modal" onClick={e => e.stopPropagation()}>
          <h2>归档分析结果</h2>
          <div className="archive-form">
            <div className="form-group">
              <label>比赛名称</label>
              <input
                type="text"
                value={archiveForm.race_name}
                onChange={e => setArchiveForm(prev => ({ ...prev, race_name: e.target.value }))}
                placeholder="如：2024年区游泳锦标赛"
              />
            </div>
            <div className="form-group">
              <label>比赛日期</label>
              <input
                type="date"
                value={archiveForm.race_date}
                onChange={e => setArchiveForm(prev => ({ ...prev, race_date: e.target.value }))}
              />
            </div>
            <div className="form-group">
              <label>比赛地点</label>
              <input
                type="text"
                value={archiveForm.race_location}
                onChange={e => setArchiveForm(prev => ({ ...prev, race_location: e.target.value }))}
                placeholder="如：市体育中心游泳馆"
              />
            </div>
          </div>
          <div className="modal-actions">
            <button className="btn btn-outline" onClick={() => setShowArchiveModal(false)}>取消</button>
            <button className="btn btn-primary" onClick={handleArchive}>确认归档</button>
          </div>
        </div>
      </div>
    )
  }

  const handleUpdateRecord = async () => {
    if (!editingRecord || editPassword !== 'ycz') { setEditError('密码错误'); return }
    const metrics: Record<string, any> = {}
    const fields = ['前程用时', '转身出水用时', '后程用时', '比赛总用时', '前程划水次数', '前程换气次数', '前程打腿次数', '后程划水次数', '后程换气次数', '后程打腿次数'] as const
    for (const f of fields) { const v = (editingRecord.analysis_result as any)?.[f]; if (v != null) metrics[f] = v }
    try {
      const res = await fetch(`${API_BASE}/records/${editingRecord.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: editPassword, swimmer_name: editingRecord.swimmer_name, pool_length: editingRecord.pool_length, race_distance: editingRecord.race_distance, stroke_type: editingRecord.stroke_type, metrics }) })
      if (res.ok) { setEditingRecord(null); setEditPassword(''); setEditError(''); fetchRecords(swimmerName); fetchAllRecords() }
      else { const d = await res.json().catch(() => ({})); setEditError(d.detail || '更新失败') }
    } catch { setEditError('网络错误') }
  }

  const renderEditRecordModal = () => {
    if (!editingRecord) return null
    const r = editingRecord
    const updateField = (key: string, val: any) => setEditingRecord({ ...r, [key]: val } as Record)
    const updateMetric = (key: string, val: any) => setEditingRecord({ ...r, analysis_result: { ...r.analysis_result, [key]: val } } as Record)
    const removeMetric = (key: string) => {
      const newResult = { ...r.analysis_result }
      delete newResult[key]
      setEditingRecord({ ...r, analysis_result: newResult } as Record)
    }
    const editNumHalves = Math.max(1, r.race_distance / 50)
    const editHalfLabels = Array.from({ length: editNumHalves }, (_, i) => `第${i + 1}半程`)
    const existingKeys = Object.keys(r.analysis_result || {})
    const legacyKeys = existingKeys.filter(k => !k.startsWith('第') && k !== '比赛总用时')
    return (
      <div className="modal-overlay" onClick={() => { setEditingRecord(null); setEditPassword(''); setEditError('') }}>
        <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 640, maxHeight: '85vh', overflowY: 'auto' }}>
          <h2>编辑比赛记录</h2>
          <div className="form-row" style={{ marginBottom: 12 }}>
            <div className="form-group"><label>运动员</label><select value={r.swimmer_name} onChange={e => updateField('swimmer_name', e.target.value)}><option value="杨钧涵">杨钧涵</option><option value="杨涴婷">杨涴婷</option></select></div>
            <div className="form-group"><label>泳姿</label><select value={r.stroke_type} onChange={e => updateField('stroke_type', e.target.value)}>{STROKE_TYPES.map(s => <option key={s} value={s}>{s}</option>)}</select></div>
            <div className="form-group"><label>泳池长度</label><select value={r.pool_length} onChange={e => updateField('pool_length', parseInt(e.target.value))}><option value={25}>25米</option><option value={50}>50米</option></select></div>
            <div className="form-group"><label>比赛距离</label><select value={r.race_distance} onChange={e => updateField('race_distance', parseInt(e.target.value))}><option value={50}>50米</option><option value={100}>100米</option><option value={200}>200米</option><option value={400}>400米</option></select></div>
          </div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, color: 'var(--primary)' }}>各半程指标（50米/半程，共{editNumHalves}个半程）</div>
          {editHalfLabels.map((label, idx) => (
            <div key={label} style={{ marginBottom: 8, padding: '8px 10px', background: idx % 2 === 0 ? 'var(--bg)' : '#fff', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--primary)', marginBottom: 4 }}>{label}（{(idx * 50) + 50}米）</div>
              <div className="form-row">
                <div className="form-group"><label>用时 (秒)</label><input type="number" step="0.001" value={(r.analysis_result as any)?.[`${label}用时`] ?? ''} onChange={e => updateMetric(`${label}用时`, e.target.value ? parseFloat(e.target.value) : null)} /></div>
                <div className="form-group"><label>划水次数</label><input type="number" step="1" value={(r.analysis_result as any)?.[`${label}划水次数`] ?? ''} onChange={e => updateMetric(`${label}划水次数`, e.target.value ? parseFloat(e.target.value) : null)} /></div>
                <div className="form-group"><label>换气次数</label><input type="number" step="1" value={(r.analysis_result as any)?.[`${label}换气次数`] ?? ''} onChange={e => updateMetric(`${label}换气次数`, e.target.value ? parseFloat(e.target.value) : null)} /></div>
                <div className="form-group"><label>打腿次数</label><input type="number" step="1" value={(r.analysis_result as any)?.[`${label}打腿次数`] ?? ''} onChange={e => updateMetric(`${label}打腿次数`, e.target.value ? parseFloat(e.target.value) : null)} /></div>
              </div>
            </div>
          ))}
          <div className="form-row" style={{ marginBottom: 12 }}>
            <div className="form-group"><label style={{ fontWeight: 600, color: 'var(--primary)' }}>比赛总用时 (秒)</label><input type="number" step="0.001" value={(r.analysis_result as any)?.['比赛总用时'] ?? ''} onChange={e => updateMetric('比赛总用时', e.target.value ? parseFloat(e.target.value) : null)} /></div>
          </div>
          {legacyKeys.length > 0 && (
            <div style={{ marginBottom: 12, padding: '8px 10px', background: '#fff8e1', borderRadius: 6, border: '1px solid #ffe082' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f57f17', marginBottom: 4 }}>旧格式指标（可清除）</div>
              <div className="form-row" style={{ flexWrap: 'wrap' }}>
                {legacyKeys.map(k => (
                  <div key={k} className="form-group" style={{ minWidth: 120 }}>
                    <label style={{ fontSize: '0.75rem' }}>{k}</label>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <input type="number" step="0.001" style={{ flex: 1 }} value={(r.analysis_result as any)?.[k] ?? ''} onChange={e => updateMetric(k, e.target.value ? parseFloat(e.target.value) : null)} />
                      <button className="btn btn-sm btn-danger" style={{ padding: '2px 6px', fontSize: '0.7rem' }} onClick={() => removeMetric(k)}>✕</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label>修改密码 *</label>
            <input type="password" value={editPassword} onChange={e => setEditPassword(e.target.value)} placeholder="请输入修改密码" />
          </div>
          {editError && <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fdecea', borderRadius: 6, fontSize: '0.85rem', color: '#b71c1c' }}>{editError}</div>}
          <div className="modal-actions">
            <button className="btn btn-outline" onClick={() => { setEditingRecord(null); setEditPassword(''); setEditError('') }}>取消</button>
            <button className="btn btn-primary" onClick={handleUpdateRecord}>确认修改</button>
          </div>
        </div>
      </div>
    )
  }

  const renderDeleteConfirmModal = () => {
    if (!deleteConfirm) return null
    return (
      <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
        <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 400 }}>
          <h2>确认删除</h2>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: 12 }}>此操作不可恢复，请输入密码确认</p>
          <div className="form-group" style={{ marginBottom: 12 }}>
            <label>密码 *</label>
            <input type="password" value={deleteConfirm.password} onChange={e => setDeleteConfirm({ ...deleteConfirm, password: e.target.value, error: '' })} placeholder="请输入密码" />
          </div>
          {deleteConfirm.error && <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fdecea', borderRadius: 6, fontSize: '0.85rem', color: '#b71c1c' }}>{deleteConfirm.error}</div>}
          <div className="modal-actions">
            <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>取消</button>
            <button className="btn btn-danger" onClick={confirmDelete}>确认删除</button>
          </div>
        </div>
      </div>
    )
  }

  const calcAge = (birthDate: string | null | undefined, raceDate: string | null | undefined): string => {
    if (!birthDate || !raceDate) return ''
    const b = new Date(birthDate), r = new Date(raceDate)
    let age = r.getFullYear() - b.getFullYear()
    const m = r.getMonth() - b.getMonth()
    if (m < 0 || (m === 0 && r.getDate() < b.getDate())) age--
    return `${age}岁`
  }

  const toggleYear = (year: string) => {
    setExpandedYears(prev => { const n = new Set(prev); n.has(year) ? n.delete(year) : n.add(year); return n })
  }
  const toggleComp = (key: string) => {
    setExpandedComps(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
  }

  const renderRecords = () => {
    if (records.length === 0) {
      return (
        <div className="card">
          <div className="card-title"><span className="icon">📋</span> 比赛记录列表</div>
          <div className="empty-state"><div className="icon">📭</div><p>暂无比赛记录</p></div>
        </div>
      )
    }

    const byYear: { [year: string]: Record[] } = {}
    records.forEach(r => {
      let year = '未知年份'
      if (r.race_date && r.race_date.length >= 4) year = r.race_date.substring(0, 4)
      else if (r.race_name) {
        const m = r.race_name.match(/(\d{4})年/)
        if (m) year = m[1]
      }
      if (year === '未知年份' && r.archive_time && r.archive_time.length >= 4) year = r.archive_time.substring(0, 4)
      if (year === '未知年份' && r.created_at && r.created_at.length >= 4) year = r.created_at.substring(0, 4)
      if (!byYear[year]) byYear[year] = []
      byYear[year].push(r)
    })
    const years = Object.keys(byYear).sort((a, b) => b.localeCompare(a))

    const strokeColors: Record<string, string> = { '自由泳': '#1a73e8', '蛙泳': '#34a853', '仰泳': '#fbbc04', '蝶泳': '#ea4335', '混合泳': '#9c27b0' }

    return (
      <div className="card" style={{ overflow: 'visible' }}>
        <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span><span className="icon">�</span> 比赛记录列表</span>
          {swimmerProfile?.birth_date && (
            <span style={{ fontSize: '0.8rem', fontWeight: 400, color: 'var(--text-secondary)', background: 'var(--primary-light)', padding: '3px 10px', borderRadius: 12 }}>
              出生日期：{swimmerProfile.birth_date}
            </span>
          )}
        </div>
        <div style={{ marginTop: 8 }}>
          {years.map(year => {
            const isYearOpen = expandedYears.has(year)
            const yearRecords = byYear[year]
            const byComp: { [comp: string]: Record[] } = {}
            yearRecords.forEach(r => {
              const comp = r.race_name || '未命名比赛'
              if (!byComp[comp]) byComp[comp] = []
              byComp[comp].push(r)
            })
            const comps = Object.keys(byComp)
            return (
              <div key={year} style={{ marginBottom: 10 }}>
                <div onClick={() => toggleYear(year)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'linear-gradient(135deg, #1a73e8 0%, #1557b0 100%)', borderRadius: 8, cursor: 'pointer', userSelect: 'none', boxShadow: '0 2px 4px rgba(26,115,232,0.2)' }}>
                  <span style={{ color: '#fff', fontSize: '0.7rem', transition: 'transform 0.2s', transform: isYearOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                  <span style={{ color: '#fff', fontWeight: 700, fontSize: '1rem', letterSpacing: 1 }}>{year}年</span>
                  <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: '0.8rem', marginLeft: 4 }}>{yearRecords.length}条记录</span>
                </div>
                {isYearOpen && (
                  <div style={{ marginLeft: 12, marginTop: 6, borderLeft: '3px solid #e8f0fe', paddingLeft: 12 }}>
                    {comps.map(comp => {
                      const compKey = `${year}-${comp}`
                      const isCompOpen = expandedComps.has(compKey)
                      const compRecords = byComp[comp]
                      const compDate = compRecords[0]?.race_date
                      const compLocation = compRecords[0]?.race_location
                      const age = calcAge(swimmerProfile?.birth_date, compDate)
                      return (
                        <div key={comp} style={{ marginBottom: 8 }}>
                          <div onClick={() => toggleComp(compKey)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: 'linear-gradient(135deg, #f8fafc 0%, #e8f0fe 100%)', borderRadius: 6, cursor: 'pointer', userSelect: 'none', border: '1px solid var(--border)' }}>
                            <span style={{ color: 'var(--primary)', fontSize: '0.65rem', transition: 'transform 0.2s', transform: isCompOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                            <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text)' }}>{comp}</span>
                            {compDate && <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginLeft: 4 }}>{compDate}</span>}
                            {compLocation && <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>· {compLocation}</span>}
                            {age && <span style={{ fontSize: '0.72rem', background: '#fff3e0', color: '#e65100', padding: '1px 6px', borderRadius: 8, marginLeft: 4 }}>{age}</span>}
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginLeft: 'auto' }}>{compRecords.length}项</span>
                          </div>
                          {isCompOpen && (
                            <div style={{ marginTop: 4 }}>
                              {compRecords.map(r => {
                                const sc = strokeColors[r.stroke_type] || 'var(--primary)'
                                const eventLabel = `${r.race_distance}米${r.stroke_type}`
                                const poolLabel = `${r.pool_length}米池`
                                return (
                                  <div key={r.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 10px', marginBottom: 4, background: '#fff', borderRadius: 6, border: '1px solid #f0f0f0', transition: 'box-shadow 0.2s' }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>{eventLabel}</span>
                                        <span style={{ fontSize: '0.7rem', background: '#f5f5f5', color: 'var(--text-secondary)', padding: '1px 6px', borderRadius: 8 }}>{poolLabel}</span>
                                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: sc, flexShrink: 0 }} />
                                      </div>
                                      {r.analysis_result && Object.keys(r.analysis_result).length > 0 && (
                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                          {Object.entries(r.analysis_result).map(([k, v]: [string, any]) => {
                                            const isTime = k.includes('用时') || k.includes('时间')
                                            return (
                                              <span key={k} style={{ fontSize: '0.72rem', background: isTime ? 'var(--primary-light)' : '#f3f4f6', color: isTime ? 'var(--primary)' : 'var(--text-secondary)', padding: '2px 7px', borderRadius: 8, fontWeight: isTime ? 500 : 400 }}>
                                                {k.replace(/用时$/, '')}: {formatMetricValue(k, v)}
                                              </span>
                                            )
                                          })}
                                        </div>
                                      )}
                                    </div>
                                    <div style={{ display: 'flex', gap: 4, flexShrink: 0, paddingTop: 2 }}>
                                      <button className="btn btn-sm btn-outline" style={{ padding: '2px 8px', fontSize: '0.75rem' }} onClick={() => setEditingRecord(r)}>编辑</button>
                                      <button className="btn btn-sm btn-danger" style={{ padding: '2px 8px', fontSize: '0.75rem' }} onClick={() => handleDeleteRecord(r.id)}>删除</button>
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const renderVideoManager = () => (
    <div className="card">
      <div className="card-title" style={{ cursor: 'pointer' }} onClick={() => { setShowVideoManager(!showVideoManager); if (!showVideoManager) fetchVideoList() }}>
        <span className="icon">🎬</span> 已上传视频管理
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: 8 }}>{showVideoManager ? '▲ 收起' : '▼ 展开'}</span>
      </div>
      {showVideoManager && (
        videoList.length === 0 ? (
          <div className="empty-state">
            <div className="icon">📭</div>
            <p>暂无已上传视频</p>
          </div>
        ) : (
          <div className="records-list">
            {videoList.map(v => (
              <div key={v.id} className="record-item">
                <div className="record-info">
                  <span className="name">
                    {v.filename}
                    <span className="badge badge-blue" style={{ marginLeft: 8 }}>{formatSize(v.file_size)}</span>
                    {v.has_analysis && <span className="badge badge-green" style={{ marginLeft: 4 }}>已分析</span>}
                    {v.archived && <span className="badge badge-green" style={{ marginLeft: 4 }}>已归档</span>}
                  </span>
                  <span className="meta">
                    上传于 {new Date(v.upload_time).toLocaleString()}
                    {v.swimmer_name ? ` · ${v.swimmer_name}` : ''}
                    {v.pool_length ? ` · ${v.pool_length}米池/${v.race_distance}米` : ''}
                    {v.race_name ? ` · ${v.race_name}` : ''}
                  </span>
                </div>
                <div className="record-actions">
                  <button className="btn btn-sm btn-primary" onClick={() => handleAnalyzeExistingVideo(v.id)}>
                    {v.has_analysis ? '重新分析' : '分析'}
                  </button>
                  {v.has_analysis && (
                    <button className="btn btn-sm btn-outline" onClick={() => {
                      fetch(`${API_BASE}/result/${v.id}`).then(r => r.json()).then(data => {
                        if (data.result) {
                          setTaskId(v.id)
                          setAnalysisResult(data.result)
                          setUploadPhase('completed')
                        }
                      }).catch(() => {})
                    }}>
                      查看结果
                    </button>
                  )}
                  <button className="btn btn-sm btn-danger" onClick={() => handleDeleteVideo(v.id)}>
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )

  const renderAnalyzeVideoModal = () => {
    if (!analyzeVideoId) return null
    const video = videoList.find(v => v.id === analyzeVideoId)
    const opts = analyzeVideoForm.race_distance === 50 && analyzeVideoForm.pool_length === 50
      ? OPTIONS_50M_50POOL : OPTIONS_50M_25POOL

    return (
      <div className="modal-overlay" onClick={() => setAnalyzeVideoId(null)}>
        <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 600 }}>
          <h2>分析视频</h2>
          {video && (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
              {video.filename} · {formatSize(video.file_size)}
            </div>
          )}

          {analyzeVideoStep === 'params' ? (
            <>
              <div className="form-row" style={{ marginBottom: 16 }}>
                <div className="form-group">
                  <label>运动员</label>
                  <select value={analyzeVideoForm.swimmer_name} onChange={e => setAnalyzeVideoForm(prev => ({ ...prev, swimmer_name: e.target.value }))}>
                    <option value="杨钧涵">杨钧涵</option>
                    <option value="杨涴婷">杨涴婷</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>泳池长度</label>
                  <select value={analyzeVideoForm.pool_length} onChange={e => setAnalyzeVideoForm(prev => ({ ...prev, pool_length: Number(e.target.value) }))}>
                    <option value={25}>25米池</option>
                    <option value={50}>50米池</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>比赛距离</label>
                  <select value={analyzeVideoForm.race_distance} onChange={e => setAnalyzeVideoForm(prev => ({ ...prev, race_distance: Number(e.target.value) }))}>
                    <option value={50}>50米</option>
                    <option value={100}>100米</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>被分析者（从左往右）</label>
                  <select value={analyzeVideoForm.swimmer_position} onChange={e => setAnalyzeVideoForm(prev => ({ ...prev, swimmer_position: Number(e.target.value) }))}>
                    {[1,2,3,4,5,6,7,8,9].map(n => (
                      <option key={n} value={n}>第{n}人</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="modal-actions">
                <button className="btn btn-outline" onClick={() => setAnalyzeVideoId(null)}>取消</button>
                <button className="btn btn-primary" onClick={() => {
                  const newOpts = analyzeVideoForm.race_distance === 50 && analyzeVideoForm.pool_length === 50
                    ? OPTIONS_50M_50POOL : OPTIONS_50M_25POOL
                  setAnalyzeVideoOptions([...newOpts])
                  setAnalyzeVideoStep('options')
                }}>下一步</button>
              </div>
            </>
          ) : (
            <>
              <div className="select-all-bar">
                <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input type="checkbox" checked={analyzeVideoOptions.length === opts.length}
                    onChange={() => setAnalyzeVideoOptions(analyzeVideoOptions.length === opts.length ? [] : [...opts])} />
                  全选
                </label>
                <span style={{ marginLeft: 'auto', color: 'var(--text-secondary)' }}>
                  已选 {analyzeVideoOptions.length}/{opts.length} 项
                </span>
              </div>
              <div className="options-grid" style={{ maxHeight: 300, overflowY: 'auto', marginBottom: 16 }}>
                {opts.map(opt => (
                  <label key={opt} className="option-item">
                    <input type="checkbox" checked={analyzeVideoOptions.includes(opt)}
                      onChange={() => setAnalyzeVideoOptions(prev =>
                        prev.includes(opt) ? prev.filter(o => o !== opt) : [...prev, opt]
                      )} />
                    {opt}
                  </label>
                ))}
              </div>
              <div className="modal-actions">
                <button className="btn btn-outline" onClick={() => setAnalyzeVideoStep('params')}>上一步</button>
                <button className="btn btn-primary" onClick={handleStartAnalyzeExisting}
                  disabled={analyzeVideoOptions.length === 0}>
                  开始分析
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  const toggleYearCollapse = (year: string) => {
    setCollapsedYears(prev => { const n = new Set(prev); n.has(year) ? n.delete(year) : n.add(year); return n })
  }


  const triggerAvatarUploadFor = (name: string) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.style.display = 'none'
    input.onchange = (ev) => {
      const file = (ev.target as HTMLInputElement).files?.[0]
      if (!file) return
      const url = URL.createObjectURL(file)
      setCropModal({ imageUrl: url, name })
      setCropArea(null)
      setCropPos({ x: 0, y: 0 })
      setCropZoom(1)
      document.body.removeChild(input)
    }
    document.body.appendChild(input)
    input.click()
  }

  const onCropComplete = useCallback((_croppedArea: any, croppedAreaPixels: any) => {
    setCropArea(croppedAreaPixels)
  }, [])

  const getCroppedImg = async (imageSrc: string, pixelCrop: { x: number; y: number; width: number; height: number }): Promise<Blob> => {
    const image = new Image()
    image.src = imageSrc
    await new Promise(resolve => { image.onload = resolve })
    const canvas = document.createElement('canvas')
    const size = Math.min(pixelCrop.width, pixelCrop.height)
    canvas.width = 256
    canvas.height = 256
    const ctx = canvas.getContext('2d')!
    ctx.beginPath()
    ctx.arc(128, 128, 128, 0, Math.PI * 2)
    ctx.clip()
    const sx = pixelCrop.x + (pixelCrop.width - size) / 2
    const sy = pixelCrop.y + (pixelCrop.height - size) / 2
    ctx.drawImage(image, sx, sy, size, size, 0, 0, 256, 256)
    return new Promise(resolve => canvas.toBlob(blob => resolve(blob!), 'image/png'))
  }

  const handleCropConfirm = async () => {
    if (!cropModal || !cropArea) return
    try {
      const blob = await getCroppedImg(cropModal.imageUrl, cropArea)
      const formData = new FormData()
      formData.append('file', blob, `${cropModal.name}.png`)
      const res = await fetch(`${API_BASE}/upload_avatar/${encodeURIComponent(cropModal.name)}`, { method: 'POST', body: formData })
      if (res.ok) {
        const data = await res.json()
        const url = data.avatar_url + '?t=' + Date.now()
        setSwimmerAvatars(prev => ({ ...prev, [cropModal.name]: url }))
        if (cropModal.name === selectedSwimmer) setAvatarUrl(url)
      }
    } catch {}
    URL.revokeObjectURL(cropModal.imageUrl)
    setCropModal(null)
  }

  const handleCropCancel = () => {
    if (cropModal) URL.revokeObjectURL(cropModal.imageUrl)
    setCropModal(null)
  }

  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `00:${seconds.toFixed(2).padStart(5, '0')}`
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`
  }

  const renderRecordDetailPage = () => {
    const byYear: { [year: string]: Record[] } = {}
    records.forEach(r => {
      let year = '未知'
      if (r.race_date && r.race_date.length >= 4) year = r.race_date.substring(0, 4)
      else if (r.race_name) { const m = r.race_name.match(/(\d{4})年/); if (m) year = m[1] }
      else if (r.archive_time && r.archive_time.length >= 4) year = r.archive_time.substring(0, 4)
      else if (r.created_at && r.created_at.length >= 4) year = r.created_at.substring(0, 4)
      if (!byYear[year]) byYear[year] = []
      byYear[year].push(r)
    })
    const years = Object.keys(byYear).sort((a, b) => b.localeCompare(a))

    const byComp: { [key: string]: { name: string; date: string | null; location: string | null; records: Record[] } } = {}
    records.forEach(r => {
      const compName = r.race_name || '未命名比赛'
      const compDate = r.race_date || null
      const key = `${compName}||${compDate || ''}`
      if (!byComp[key]) byComp[key] = { name: compName, date: compDate, location: r.race_location, records: [] }
      byComp[key].records.push(r)
    })
    const compList = Object.values(byComp).sort((a, b) => (b.date || '').localeCompare(a.date || ''))

    const renderListPage = () => (
      <div className="m-page">
        <div className="m-navbar">
          <div className="m-nav-btn" onClick={() => triggerAvatarUploadFor(selectedSwimmer)}>📷</div>
          <div className="m-nav-title">赛事</div>
        </div>
        <div className="m-content">
          {years.length === 0 && <div className="m-empty">- 暂无赛事 -</div>}
          {years.map(year => {
            const yearComps = compList.filter(c => c.records.some(r => {
              let y = '未知'
              if (r.race_date && r.race_date.length >= 4) y = r.race_date.substring(0, 4)
              else if (r.race_name) { const m = r.race_name.match(/(\d{4})年/); if (m) y = m[1] }
              else if (r.archive_time && r.archive_time.length >= 4) y = r.archive_time.substring(0, 4)
              else if (r.created_at && r.created_at.length >= 4) y = r.created_at.substring(0, 4)
              return y === year
            }))
            const isOpen = !collapsedYears.has(year)
            return (
              <div key={year}>
                <div className="m-year-bar" onClick={() => toggleYearCollapse(year)}>
                  <span className="m-year-text">{year}年</span>
                  <span className="m-year-arrow" style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>›</span>
                </div>
                {isOpen && (
                  yearComps.length === 0 ? <div className="m-empty">- 暂无赛事 -</div> :
                  yearComps.map((comp, idx) => (
                    <div key={idx} className="m-event-card" onClick={() => { setSelectedComp(comp); setRecordSubPage('detail') }}>
                      <div className="m-event-name">{comp.name}</div>
                      <div className="m-event-time">{comp.date || ''}</div>
                      <span className="m-event-arrow">›</span>
                    </div>
                  ))
                )}
              </div>
            )
          })}
        </div>
      </div>
    )

    const renderDetailPage = () => {
      if (!selectedComp) return null
      const compRecords = selectedComp.records
      return (
        <div className="m-page">
          <div className="m-navbar">
            <div className="m-nav-back" onClick={() => setRecordSubPage('list')}>‹</div>
            <div className="m-nav-btn" onClick={() => triggerAvatarUploadFor(selectedSwimmer)}>📷</div>
            <div className="m-nav-title" style={{ fontSize: '0.95rem' }}>{selectedComp.name}</div>
          </div>
          <div className="m-content">
            <div className="m-athlete-card">
              <div className="m-athlete-left">
                <div className="m-athlete-name">{selectedSwimmer}</div>
                <div className="m-athlete-meta">
                  {swimmerProfile?.birth_date && <span>{swimmerProfile.birth_date.substring(0, 4)}年</span>}
                </div>
              </div>
            </div>
            {compRecords.map(r => {
              const totalTime = r.analysis_result?.['比赛总用时']
              const eventLabel = `${r.race_distance}米${r.stroke_type}`
              return (
                <div key={r.id} className="m-proj-card" onClick={() => { setSelectedEvent(r); setLiked(false); setPopularity(0); setRecordSubPage('result') }}>
                  <div className="m-proj-left">
                    <div className="m-proj-name">{eventLabel}</div>
                    <div className="m-proj-meta">{selectedComp.date || ''} · 决赛 · 已结束</div>
                  </div>
                  <div className="m-proj-right">
                    {totalTime != null && <div className="m-proj-score">成绩：{formatTime(totalTime)}</div>}
                    <span className="m-event-arrow">›</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )
    }

    const renderResultPage = () => {
      if (!selectedEvent) return null
      const r = selectedEvent
      const ar = r.analysis_result || {}
      const totalTime = ar['比赛总用时']
      const eventLabel = `${r.race_distance}米${r.stroke_type}`
      const title = `${eventLabel} 决赛`

      const numHalves = Math.max(1, r.race_distance / 50)
      const halfLabels = Array.from({ length: numHalves }, (_, i) => `第${i + 1}半程`)

      return (
        <div className="m-page">
          <div className="m-navbar">
            <div className="m-nav-back" onClick={() => setRecordSubPage('detail')}>‹</div>
            <div className="m-nav-btn" onClick={() => triggerAvatarUploadFor(selectedSwimmer)}>📷</div>
            <div className="m-nav-title" style={{ fontSize: '0.95rem' }}>{title}</div>
          </div>
          <div className="m-content">
            <div className="m-result-athlete">
              <div className="m-result-name">{selectedSwimmer}</div>
              <div className="m-result-meta">
                {swimmerProfile?.birth_date && <span>{swimmerProfile.birth_date.substring(0, 4)}年</span>}
                <span style={{ marginLeft: 6 }}>{r.pool_length}米池</span>
              </div>
            </div>
            <div className="m-score-row">
              <div className="m-score-col">
                <div className="m-score-label">名次</div>
                <div className="m-score-rank">-</div>
              </div>
              <div className="m-score-col">
                <div className="m-score-label">成绩</div>
                <div className="m-score-time">{totalTime != null ? formatTime(totalTime) : '-'}</div>
              </div>
            </div>
            {halfLabels.some(l => ar[`${l}用时`] != null) && (
              <div className="m-data-card">
                <div className="m-data-grid3">
                  {halfLabels.map((label) => {
                    const t = ar[`${label}用时`]
                    if (t == null) return null
                    return (
                      <div key={label} className="m-data-item">
                        <div className="m-data-label">{label}</div>
                        <div className="m-data-value">{formatTime(t)}</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
            <div className="m-data-card">
              <table className="m-seg-table">
                <thead>
                  <tr>
                    <th>分段距离</th>
                    <th>成绩</th>
                    <th>时间差</th>
                  </tr>
                </thead>
                <tbody>
                  {halfLabels.map((label, idx) => {
                    const t = ar[`${label}用时`]
                    if (t == null) return null
                    return (
                      <tr key={label}>
                        <td>{(idx + 1) * 50}m</td>
                        <td style={{ fontFamily: "'SF Mono', Menlo, Monaco, monospace" }}>{formatTime(t)}</td>
                        <td>{idx === 0 ? '-' : formatTime(t)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {halfLabels.some(l => ar[`${l}划水次数`] != null || ar[`${l}换气次数`] != null || ar[`${l}打腿次数`] != null) && (
              <div className="m-data-card">
                <div className="m-data-title">技术指标</div>
                <table className="m-seg-table">
                  <thead>
                    <tr>
                      <th>半程</th>
                      <th>划水</th>
                      <th>换气</th>
                      <th>打腿</th>
                    </tr>
                  </thead>
                  <tbody>
                    {halfLabels.map((label) => {
                      const stroke = ar[`${label}划水次数`]
                      const breath = ar[`${label}换气次数`]
                      const kick = ar[`${label}打腿次数`]
                      if (stroke == null && breath == null && kick == null) return null
                      return (
                        <tr key={label}>
                          <td>{label}</td>
                          <td>{stroke ?? '-'}</td>
                          <td>{breath ?? '-'}</td>
                          <td>{kick ?? '-'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {r.linked_video_id && (
              <div className="m-data-card" style={{ cursor: 'pointer' }} onClick={() => { setPage('video', { videoId: r.linked_video_id }) }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: '1.2rem' }}>🎥</span>
                  <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--primary)' }}>查看关联视频</span>
                  <span style={{ marginLeft: 'auto', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>›</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )
    }

    return recordSubPage === 'result' ? renderResultPage() : recordSubPage === 'detail' ? renderDetailPage() : renderListPage()
  }

  const renderEntryPage = () => (
    <div className="swimmer-page-bg">
      <div className="container" style={{ paddingTop: 16 }}>
        <ManualEntryCard swimmerName={selectedSwimmer} onSaved={() => { fetchRecords(selectedSwimmer); fetchAllRecords() }} />
      </div>
    </div>
  )

  const renderVideoPage = () => (
    <div className="swimmer-page-bg">
      <div className="container" style={{ paddingTop: 16 }}>
        <VideoManager />
      </div>
    </div>
  )

  const [comp1Swimmer, setComp1Swimmer] = useState('')
  const [comp1Year, setComp1Year] = useState('')
  const [comp1Race, setComp1Race] = useState('')
  const [comp1Event, setComp1Event] = useState('')
  const [comp2Swimmer, setComp2Swimmer] = useState('')
  const [comp2Year, setComp2Year] = useState('')
  const [comp2Race, setComp2Race] = useState('')
  const [comp2Event, setComp2Event] = useState('')
  const compareRef = useRef<HTMLDivElement>(null)

  const getYear = (r: any) => { if (r.race_date && r.race_date.length >= 4) return r.race_date.substring(0, 4); if (r.race_name) { const m = r.race_name.match(/(\d{4})年/); if (m) return m[1] } return '未知' }

  const compSwimmers = [...new Set(allRecords.map(r => r.swimmer_name))]
  const comp1Years = comp1Swimmer ? [...new Set(allRecords.filter(r => r.swimmer_name === comp1Swimmer).map(getYear))].sort((a, b) => b.localeCompare(a)) : []
  const comp1Races = (comp1Swimmer && comp1Year) ? [...new Map(allRecords.filter(r => r.swimmer_name === comp1Swimmer && getYear(r) === comp1Year).map(r => [r.race_name || '未命名', r.race_name || '未命名'])).values()] : []
  const comp1Events = (comp1Swimmer && comp1Year && comp1Race) ? allRecords.filter(r => r.swimmer_name === comp1Swimmer && getYear(r) === comp1Year && (r.race_name || '未命名') === comp1Race) : []
  const comp2Years = comp2Swimmer ? [...new Set(allRecords.filter(r => r.swimmer_name === comp2Swimmer).map(getYear))].sort((a, b) => b.localeCompare(a)) : []
  const comp2Races = (comp2Swimmer && comp2Year) ? [...new Map(allRecords.filter(r => r.swimmer_name === comp2Swimmer && getYear(r) === comp2Year).map(r => [r.race_name || '未命名', r.race_name || '未命名'])).values()] : []
  const comp2Events = (comp2Swimmer && comp2Year && comp2Race) ? allRecords.filter(r => r.swimmer_name === comp2Swimmer && getYear(r) === comp2Year && (r.race_name || '未命名') === comp2Race) : []

  const formatCompTime = (s: number) => { if (s < 60) return s.toFixed(2) + '秒'; const m = Math.floor(s / 60); const sec = s % 60; return m + '分' + sec.toFixed(2).padStart(5, '0') + '秒' }

  const handleCompareDownload = async () => {
    if (!compareRef.current) return
    try {
      const html2canvas = (await import('html2canvas' as any)).default
      const canvas = await html2canvas(compareRef.current, { backgroundColor: '#FFFFFF', scale: 2 })
      const link = document.createElement('a')
      link.download = '对比结果.png'
      link.href = canvas.toDataURL('image/png')
      link.click()
    } catch {
      const canvas = document.createElement('canvas')
      canvas.width = 800; canvas.height = 600
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 800, 600)
      ctx.fillStyle = '#333'; ctx.font = '20px sans-serif'; ctx.fillText('对比结果', 40, 40)
      const link = document.createElement('a')
      link.download = '对比结果.png'
      link.href = canvas.toDataURL('image/png')
      link.click()
    }
  }


  const renderComparePage = () => {
    const S: React.CSSProperties = { padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem', width: '100%' }
    return (
    <>
      <div className="card">
        <div className="card-title"><span className="icon">⚖️</span> 对比分析</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 16 }}>
          分别选择两条记录进行逐项对比
        </p>
        <div style={{ marginBottom: 12, padding: '10px 12px', background: '#EFF6FF', borderRadius: 8, border: '1px solid #BFDBFE' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1677FF', marginBottom: 8 }}>📋 记录 1</div>
          <div className="form-row" style={{ marginBottom: 8 }}>
            <div className="form-group">
              <label>运动员</label>
              <select style={S} value={comp1Swimmer} onChange={e => { setComp1Swimmer(e.target.value); setComp1Year(''); setComp1Race(''); setComp1Event(''); setCompareData(null) }}>
                <option value="">请选择</option>
                {compSwimmers.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>年份</label>
              <select style={S} value={comp1Year} onChange={e => { setComp1Year(e.target.value); setComp1Race(''); setComp1Event(''); setCompareData(null) }} disabled={!comp1Swimmer}>
                <option value="">请选择</option>
                {comp1Years.map(y => <option key={y} value={y}>{y}年</option>)}
              </select>
            </div>
          </div>
          <div className="form-row" style={{ marginBottom: 8 }}>
            <div className="form-group">
              <label>比赛</label>
              <select style={S} value={comp1Race} onChange={e => { setComp1Race(e.target.value); setComp1Event(''); setCompareData(null) }} disabled={!comp1Year}>
                <option value="">请选择</option>
                {comp1Races.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>项目</label>
              <select style={S} value={comp1Event} onChange={e => { setComp1Event(e.target.value); setCompareData(null) }} disabled={!comp1Race}>
                <option value="">请选择</option>
                {comp1Events.map(r => <option key={r.id} value={r.id}>{r.race_distance}米{r.stroke_type}</option>)}
              </select>
            </div>
          </div>
        </div>
        <div style={{ marginBottom: 12, padding: '10px 12px', background: '#ECFDF5', borderRadius: 8, border: '1px solid #A7F3D0' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#10B981', marginBottom: 8 }}>📋 记录 2</div>
          <div className="form-row" style={{ marginBottom: 8 }}>
            <div className="form-group">
              <label>运动员</label>
              <select style={S} value={comp2Swimmer} onChange={e => { setComp2Swimmer(e.target.value); setComp2Year(''); setComp2Race(''); setComp2Event(''); setCompareData(null) }}>
                <option value="">请选择</option>
                {compSwimmers.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>年份</label>
              <select style={S} value={comp2Year} onChange={e => { setComp2Year(e.target.value); setComp2Race(''); setComp2Event(''); setCompareData(null) }} disabled={!comp2Swimmer}>
                <option value="">请选择</option>
                {comp2Years.map(y => <option key={y} value={y}>{y}年</option>)}
              </select>
            </div>
          </div>
          <div className="form-row" style={{ marginBottom: 8 }}>
            <div className="form-group">
              <label>比赛</label>
              <select style={S} value={comp2Race} onChange={e => { setComp2Race(e.target.value); setComp2Event(''); setCompareData(null) }} disabled={!comp2Year}>
                <option value="">请选择</option>
                {comp2Races.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>项目</label>
              <select style={S} value={comp2Event} onChange={e => { setComp2Event(e.target.value); setCompareData(null) }} disabled={!comp2Race}>
                <option value="">请选择</option>
                {comp2Events.map(r => <option key={r.id} value={r.id}>{r.race_distance}米{r.stroke_type}</option>)}
              </select>
            </div>
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => { setCompareId1(comp1Event); setCompareId2(comp2Event); handleCompare() }} disabled={!comp1Event || !comp2Event || comp1Event === comp2Event} style={{ width: '100%' }}>
          开始对比
        </button>
      </div>

      {compareData && (() => {
        const r1 = compareData.record1
        const r2 = compareData.record2
        const ar1 = r1.analysis_result || {}
        const ar2 = r2.analysis_result || {}
        const halfKeys = Array.from({ length: 8 }, (_, i) => i + 1).map(i => ({
          time: `第${i}半程用时`, stroke: `第${i}半程划水次数`, breath: `第${i}半程换气次数`, kick: `第${i}半程打腿次数`
        })).filter(h => ar1[h.time] != null || ar2[h.time] != null)
        const totalKey = '比赛总用时'
        const getVal = (ar: any, key: string) => { const v = ar[key]; return v != null ? (typeof v === 'number' ? v : parseFloat(v)) : null }
        const diffColor = (d: number | null, lowerBetter: boolean = true) => {
          if (d == null) return '#999'
          if (d === 0) return '#999'
          const improved = lowerBetter ? d < 0 : d > 0
          return improved ? '#10B981' : '#F53F3F'
        }
        return (
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div className="card-title" style={{ marginBottom: 0 }}><span className="icon">📊</span> 对比结果</div>
              <button className="btn btn-sm btn-outline" onClick={handleCompareDownload} style={{ color: 'var(--primary)' }}>📥 下载图片</button>
            </div>
            <div ref={compareRef} style={{ background: '#fff', padding: 16, borderRadius: 12 }}>
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1A1A1A' }}>成绩对比</div>
              </div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                {[r1, r2].map((rec, idx) => (
                  <div key={idx} style={{ flex: 1, background: idx === 0 ? '#EFF6FF' : '#ECFDF5', borderRadius: 8, padding: '10px 12px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.8rem', color: '#86909C' }}>记录 {idx + 1}</div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, marginTop: 2 }}>{rec.swimmer_name}</div>
                    <div style={{ fontSize: '0.9rem', fontWeight: 600, marginTop: 2 }}>{rec.race_distance}米{rec.stroke_type}</div>
                    <div style={{ fontSize: '0.72rem', color: '#86909C', marginTop: 2 }}>{rec.race_name || ''}</div>
                    <div style={{ fontSize: '0.72rem', color: '#86909C', marginTop: 1 }}>{rec.race_date || ''}</div>
                  </div>
                ))}
              </div>
              {getVal(ar1, totalKey) != null && getVal(ar2, totalKey) != null && (() => {
                const t1 = getVal(ar1, totalKey)!, t2 = getVal(ar2, totalKey)!, d = t2 - t1
                return (
                  <div style={{ background: '#F7F8FA', borderRadius: 8, padding: '12px 16px', marginBottom: 16, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.8rem', color: '#86909C', marginBottom: 6 }}>总成绩</div>
                    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 24 }}>
                      <div><div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#1677FF' }}>{formatCompTime(t1)}</div></div>
                      <div style={{ fontSize: '1.2rem', color: '#999' }}>VS</div>
                      <div><div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10B981' }}>{formatCompTime(t2)}</div></div>
                    </div>
                    <div style={{ marginTop: 8, fontSize: '0.9rem', fontWeight: 600, color: diffColor(d) }}>
                      {d > 0 ? '+' : ''}{d.toFixed(2)}秒 {d < 0 ? '进步' : d > 0 ? '退步' : '持平'}
                    </div>
                  </div>
                )
              })()}
              {halfKeys.map((h, idx) => {
                const ht1 = getVal(ar1, h.time), ht2 = getVal(ar2, h.time)
                const hs1 = getVal(ar1, h.stroke), hs2 = getVal(ar2, h.stroke)
                const hb1 = getVal(ar1, h.breath), hb2 = getVal(ar2, h.breath)
                const hk1 = getVal(ar1, h.kick), hk2 = getVal(ar2, h.kick)
                const td = (ht1 != null && ht2 != null) ? ht2! - ht1! : null
                return (
                  <div key={idx} style={{ background: idx % 2 === 0 ? '#F7F8FA' : '#fff', borderRadius: 8, padding: '10px 14px', marginBottom: 8 }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#1677FF', marginBottom: 6 }}>第{idx + 1}半程（{(idx + 1) * 50}米）</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4, fontSize: '0.8rem' }}>
                      <div style={{ color: '#86909C' }}>指标</div>
                      <div style={{ textAlign: 'center', color: '#1677FF' }}>记录1</div>
                      <div style={{ textAlign: 'center', color: '#10B981' }}>记录2</div>
                      {ht1 != null || ht2 != null ? (<><div>用时</div><div style={{ textAlign: 'center' }}>{ht1 != null ? ht1.toFixed(2) : '-'}</div><div style={{ textAlign: 'center' }}>{ht2 != null ? ht2.toFixed(2) : '-'}</div></>) : null}
                      {hs1 != null || hs2 != null ? (<><div>划水</div><div style={{ textAlign: 'center' }}>{hs1 ?? '-'}</div><div style={{ textAlign: 'center' }}>{hs2 ?? '-'}</div></>) : null}
                      {hb1 != null || hb2 != null ? (<><div>换气</div><div style={{ textAlign: 'center' }}>{hb1 ?? '-'}</div><div style={{ textAlign: 'center' }}>{hb2 ?? '-'}</div></>) : null}
                      {hk1 != null || hk2 != null ? (<><div>打腿</div><div style={{ textAlign: 'center' }}>{hk1 ?? '-'}</div><div style={{ textAlign: 'center' }}>{hk2 ?? '-'}</div></>) : null}
                    </div>
                    {td != null && (
                      <div style={{ marginTop: 4, fontSize: '0.78rem', fontWeight: 600, color: diffColor(td) }}>
                        用时差: {td > 0 ? '+' : ''}{td.toFixed(2)}秒 {td < 0 ? '进步' : td > 0 ? '退步' : '持平'}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}
    </>
  )
  }


  const [extraSwimmers, setExtraSwimmers] = useState<string[]>([])

  const allSwimmerNames = () => {
    const names = ['杨钧涵', '杨涴婷']
    extraSwimmers.forEach(n => { if (!names.includes(n)) names.push(n) })
    return names
  }

  const swimmerColors = ['#4F95FF', '#10B981', '#9333EA', '#F59E0B', '#EF4444', '#EC4899']

  const selectSwimmerForRecords = (name: string) => {
    if (name === '__add__') {
      const inputName = prompt('请输入运动员姓名：')
      if (!inputName || allSwimmerNames().includes(inputName)) return
      setExtraSwimmers(prev => [...prev, inputName])
      setSelectedSwimmer(inputName)
    } else {
      setSelectedSwimmer(name)
    }
    setPage('record-detail', { swimmer: name })
  }

  const renderHomePage = () => (
    <div className="home-page">
      <div className="home-hero">
        <h1 className="home-title">🏊 泳娃比赛记录平台</h1>
        <p className="home-subtitle">游泳比赛成绩记录与分析</p>
        <div className="home-wave">
          <svg viewBox="0 0 1440 120" preserveAspectRatio="none">
            <path d="M0,60 C360,120 720,0 1080,60 C1260,90 1380,40 1440,60 L1440,120 L0,120 Z" fill="rgba(255,255,255,0.3)" />
            <path d="M0,80 C360,20 720,100 1080,40 C1260,20 1380,80 1440,60 L1440,120 L0,120 Z" fill="rgba(255,255,255,0.2)" />
          </svg>
        </div>
      </div>
      <div className="home-modules">
        <div className="module-card" onClick={() => setPage('records')}>
          <div className="module-icon" style={{ background: 'linear-gradient(135deg, #4F95FF 0%, #60A5FA 100%)' }}>📋</div>
          <div className="module-name">比赛记录</div>
          <div className="module-desc">查看历史成绩</div>
        </div>
        <div className="module-card" onClick={() => setPage('video')}>
          <div className="module-icon" style={{ background: 'linear-gradient(135deg, #10B981 0%, #34D399 100%)' }}>🎬</div>
          <div className="module-name">比赛视频</div>
          <div className="module-desc">上传与管理</div>
        </div>
        <div className="module-card" onClick={() => setPage('compare')}>
          <div className="module-icon" style={{ background: 'linear-gradient(135deg, #F59E0B 0%, #FBBF24 100%)' }}>⚖️</div>
          <div className="module-name">对比分析</div>
          <div className="module-desc">成绩对比</div>
        </div>
        <div className="module-card" onClick={() => setPage('entry')}>
          <div className="module-icon" style={{ background: 'linear-gradient(135deg, #9333EA 0%, #A855F7 100%)' }}>✏️</div>
          <div className="module-name">比赛录入</div>
          <div className="module-desc">录入新记录</div>
        </div>
      </div>
    </div>
  )

  const renderRecordsPage = () => (
    <div className="swimmer-page-bg">
      <header className="header">
        <div className="header-inner">
          <button className="btn btn-sm btn-outline back-btn" onClick={() => setPage('home')}>← 返回</button>
          <div className="header-center"><h1>比赛记录</h1></div>
          <div style={{ width: 60 }}></div>
        </div>
      </header>
      <div className="home-avatars" style={{ paddingTop: 40, paddingBottom: 40 }}>
        {allSwimmerNames().map((name, idx) => (
          <div key={name} className="avatar-card" onClick={() => selectSwimmerForRecords(name)}>
            <div className="avatar-circle" style={{ overflow: 'hidden' }}>
              {swimmerAvatars[name] ? <img src={swimmerAvatars[name]} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} /> : <span className="avatar-emoji">🏊‍♀️</span>}
            </div>
            <div className="avatar-name">{name}</div>
          </div>
        ))}
        <div key="__add__" className="avatar-card" onClick={() => selectSwimmerForRecords('__add__')}>
          <div className="avatar-circle" style={{ borderColor: '#D1D5DB', borderStyle: 'dashed' }}>
            <span className="avatar-emoji" style={{ fontSize: '2rem', color: '#9CA3AF' }}>+</span>
          </div>
          <div className="avatar-name" style={{ color: '#9CA3AF' }}>添加</div>
        </div>
      </div>
    </div>
  )

  const getPageTitle = () => {
    switch (page) {
      case 'record-detail': return selectedSwimmer
      case 'video': return '比赛视频'
      case 'compare': return '对比分析'
      case 'entry': return '比赛录入'
      default: return ''
    }
  }

  const goBack = () => {
    if (page === 'record-detail') {
      if (recordSubPage === 'result') { setRecordSubPage('detail'); return }
      if (recordSubPage === 'detail') { setRecordSubPage('list'); return }
    }
    window.history.back()
  }

  return (
    <div>
      {page === 'home' ? (
        <>
          {renderHomePage()}
          {renderEditRecordModal()}
          {renderDeleteConfirmModal()}
        </>
      ) : page === 'records' ? (
        <>
          {renderRecordsPage()}
          {renderEditRecordModal()}
          {renderDeleteConfirmModal()}
        </>
      ) : (
        <>
          <header className="header">
            <div className="header-inner">
              <button className="btn btn-sm btn-outline back-btn" onClick={goBack}>← 返回</button>
              <div className="header-center"><h1>{getPageTitle()}</h1></div>
              <div style={{ width: 60 }}></div>
            </div>
          </header>
          <main className="main">
            {page === 'record-detail' ? renderRecordDetailPage() :
             page === 'video' ? renderVideoPage() :
             page === 'entry' ? renderEntryPage() :
             page === 'compare' ? (
               <div className="swimmer-page-bg">
                 <div className="container" style={{ paddingTop: 16 }}>
                   {renderComparePage()}
                 </div>
               </div>
             ) : null}
          </main>
          <UploadStatusBar />
          {renderEditRecordModal()}
          {renderDeleteConfirmModal()}
          {cropModal && (
            <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.85)', zIndex: 3000, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ position: 'relative', width: '90vw', maxWidth: 400, height: '60vh', background: '#333', borderRadius: 8, overflow: 'hidden' }}>
                <Cropper
                  image={cropModal.imageUrl}
                  crop={cropPos}
                  zoom={cropZoom}
                  aspect={1}
                  cropShape="round"
                  onCropChange={setCropPos}
                  onZoomChange={setCropZoom}
                  onCropComplete={onCropComplete}
                />
              </div>
              <div style={{ width: '90vw', maxWidth: 400, marginTop: 16, display: 'flex', alignItems: 'center', gap: 12, color: '#fff', fontSize: '0.85rem' }}>
                <span>−</span>
                <input type="range" min={1} max={3} step={0.05} value={cropZoom} onChange={e => setCropZoom(Number(e.target.value))} style={{ flex: 1, accentColor: '#1677FF' }} />
                <span>+</span>
              </div>
              <div style={{ display: 'flex', gap: 16, marginTop: 16 }}>
                <button onClick={handleCropCancel} style={{ padding: '10px 28px', borderRadius: 8, border: '1px solid #fff', background: 'transparent', color: '#fff', fontSize: '1rem', cursor: 'pointer' }}>取消</button>
                <button onClick={handleCropConfirm} style={{ padding: '10px 28px', borderRadius: 8, border: 'none', background: '#1677FF', color: '#fff', fontSize: '1rem', cursor: 'pointer', fontWeight: 600 }}>确认</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

const STROKE_TYPES = ['自由泳', '蛙泳', '仰泳', '蝶泳']

interface Competition {
  id: string
  name: string
  date: string | null
  location: string | null
}

const ManualEntryCard: React.FC<{ swimmerName?: string; onSaved: () => void }> = ({ swimmerName: defaultName, onSaved }) => {
  const [swimmerName, setSwimmerName] = useState(defaultName || '杨钧涵')
  const [swimmerList, setSwimmerList] = useState<string[]>(['杨钧涵', '杨涴婷'])
  const [strokeType, setStrokeType] = useState('自由泳')
  const [poolLength, setPoolLength] = useState(50)
  const [raceDistance, setRaceDistance] = useState(100)
  const [halfMetrics, setHalfMetrics] = useState<Record<string, string>>({})
  const [totalTime, setTotalTime] = useState('')
  const [raceYear, setRaceYear] = useState(new Date().getFullYear().toString())
  const [raceMonth, setRaceMonth] = useState((new Date().getMonth() + 1).toString().padStart(2, '0'))
  const [saving, setSaving] = useState(false)
  const [videos, setVideos] = useState<any[]>([])
  const [linkedVideoId, setLinkedVideoId] = useState('')
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [selectedCompId, setSelectedCompId] = useState('')
  const [showNewComp, setShowNewComp] = useState(false)
  const [newComp, setNewComp] = useState({ name: '', date: '', location: '' })
  const [creatingComp, setCreatingComp] = useState(false)
  const [recognizing, setRecognizing] = useState(false)
  const [recognizeError, setRecognizeError] = useState('')
  const [recognizePreview, setRecognizePreview] = useState<string | null>(null)
  const [showImageModal, setShowImageModal] = useState(false)
  const [imageFile, setImageFile] = useState<File | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)
  const [compRecognizing, setCompRecognizing] = useState(false)
  const compFileInputRef = React.useRef<HTMLInputElement>(null)
  const [recognizedComps, setRecognizedComps] = useState<{ name: string; date: string; location: string }[]>([])
  const [duplicateCheck, setDuplicateCheck] = useState<any>(null)
  const [overwritePw, setOverwritePw] = useState('')

  const numHalves = Math.max(1, raceDistance / 50)
  const halfLabels = Array.from({ length: numHalves }, (_, i) => `第${i + 1}半程`)

  const fetchCompetitions = () => { fetch(`${API_BASE}/competitions`).then(r => r.ok ? r.json() : []).then(setCompetitions).catch(() => {}) }

  const fetchSwimmers = () => {
    fetch(`${API_BASE}/all_records`).then(r => r.ok ? r.json() : []).then((recs: any[]) => {
      const names = new Set<string>(['杨钧涵', '杨涴婷'])
      recs.forEach((r: any) => { if (r.swimmer_name) names.add(r.swimmer_name) })
      setSwimmerList(Array.from(names))
    }).catch(() => {})
  }

  useEffect(() => { fetch(`${API_BASE}/videos/list`).then(r => r.ok ? r.json() : []).then(setVideos).catch(() => {}); fetchCompetitions(); fetchSwimmers() }, [])

  const handleCreateComp = async () => {
    if (!newComp.name) return
    setCreatingComp(true)
    try {
      const res = await fetch(`${API_BASE}/competitions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newComp) })
      if (res.ok) {
        const data = await res.json()
        fetchCompetitions()
        setSelectedCompId(data.id)
        setShowNewComp(false)
        setNewComp({ name: '', date: '', location: '' })
      }
    } catch {}
    setCreatingComp(false)
  }

  const handleCompFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setCompRecognizing(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/recognize_competition`, { method: 'POST', body: formData })
      if (res.ok) {
        const data = await res.json()
        if (data.data) {
          const d = data.data
          let comps = []
          if (Array.isArray(d)) { comps = d }
          else if (d.competitions && Array.isArray(d.competitions)) { comps = d.competitions }
          else if (d.name) { comps = [d] }
          if (comps.length === 1) {
            setNewComp(prev => ({ name: comps[0].name || prev.name, date: comps[0].date || prev.date, location: comps[0].location || prev.location }))
            setRecognizedComps([])
          } else if (comps.length > 1) {
            setRecognizedComps(comps.map((c: any) => ({ name: c.name || '', date: c.date || '', location: c.location || '' })))
          }
        }
      }
    } catch {}
    setCompRecognizing(false)
    e.target.value = ''
  }

  const handleSaveRecognizedComp = async (comp: { name: string; date: string; location: string }) => {
    if (!comp.name) return
    const res = await fetch(`${API_BASE}/competitions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(comp) })
    if (res.ok) { fetchCompetitions(); setRecognizedComps(prev => prev.filter(c => c !== comp)) }
  }

  const handleSaveAllRecognized = async () => {
    for (const comp of recognizedComps) {
      if (!comp.name) continue
      await fetch(`${API_BASE}/competitions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(comp) })
    }
    fetchCompetitions()
    setRecognizedComps([])
  }

  const applyRecognition = (d: any) => {
    if (d.stroke_type) setStrokeType(d.stroke_type)
    if (d.pool_length) setPoolLength(d.pool_length)
    if (d.race_distance) setRaceDistance(d.race_distance)
    const newMetrics: Record<string, string> = {}
    for (let i = 1; i <= 8; i++) {
      const label = `第${i}半程`
      if (d[`${label}用时`] != null) newMetrics[`${label}用时`] = String(d[`${label}用时`])
      if (d[`${label}划水次数`] != null) newMetrics[`${label}划水次数`] = String(d[`${label}划水次数`])
      if (d[`${label}换气次数`] != null) newMetrics[`${label}换气次数`] = String(d[`${label}换气次数`])
      if (d[`${label}打腿次数`] != null) newMetrics[`${label}打腿次数`] = String(d[`${label}打腿次数`])
    }
    if (d['比赛总用时'] != null) setTotalTime(String(d['比赛总用时']))
    setHalfMetrics(prev => ({ ...prev, ...newMetrics }))
    if (d.race_name) {
      const rn = d.race_name.trim()
      const existing = competitions.find(c => c.name === rn || c.name.includes(rn) || rn.includes(c.name))
      if (existing) {
        setSelectedCompId(existing.id)
        if (existing.date) {
          const parts = existing.date.split('-')
          if (parts[0]) setRaceYear(parts[0])
          if (parts[1]) setRaceMonth(parts[1].padStart(2, '0'))
        }
      } else {
        setSelectedCompId('')
        setShowNewComp(true)
        setNewComp(prev => ({ ...prev, name: rn, date: d.race_date || '', location: d.race_location || '' }))
      }
    }
    if (d.race_date) {
      const parts = String(d.race_date).split('-')
      if (parts[0]) setRaceYear(parts[0])
      if (parts[1]) setRaceMonth(parts[1].padStart(2, '0'))
    }
  }

  const doRecognize = async (file: File) => {
    setRecognizing(true); setRecognizeError('')
    const formData = new FormData(); formData.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/recognize_image`, { method: 'POST', body: formData })
      if (res.ok) {
        const data = await res.json()
        if (data.data) applyRecognition(data.data)
      } else {
        const err = await res.json().catch(() => ({}))
        setRecognizeError(err.detail || '识别失败')
      }
    } catch { setRecognizeError('网络错误') }
    setRecognizing(false)
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImageFile(file)
    if (recognizePreview) URL.revokeObjectURL(recognizePreview)
    setRecognizePreview(URL.createObjectURL(file))
    doRecognize(file)
    e.target.value = ''
  }

  const handleReRecognize = () => {
    if (!imageFile || recognizing) return
    doRecognize(imageFile)
  }

  const resetForm = () => {
    setStrokeType('自由泳')
    setPoolLength(50)
    setRaceDistance(100)
    setHalfMetrics({})
    setTotalTime('')
    setRaceYear(new Date().getFullYear().toString())
    setRaceMonth((new Date().getMonth() + 1).toString().padStart(2, '0'))
    setLinkedVideoId('')
    setSelectedCompId('')
    setShowNewComp(false)
    setNewComp({ name: '', date: '', location: '' })
    setRecognizeError('')
    setImageFile(null)
    setDuplicateCheck(null)
    setOverwritePw('')
    if (recognizePreview) { URL.revokeObjectURL(recognizePreview); setRecognizePreview(null) }
    fetchSwimmers()
  }

  const handleSave = async () => {
    setSaving(true)
    const metrics: Record<string, any> = {}
    for (const label of halfLabels) {
      const timeKey = `${label}用时`
      if (halfMetrics[timeKey]) metrics[timeKey] = parseFloat(halfMetrics[timeKey])
      for (const tech of ['划水次数', '换气次数', '打腿次数']) {
        const k = `${label}${tech}`
        if (halfMetrics[k]) metrics[k] = parseFloat(halfMetrics[k])
      }
    }
    if (totalTime) metrics['比赛总用时'] = parseFloat(totalTime)

    try {
      let compId = selectedCompId
      if (!compId && newComp.name) {
        const compRes = await fetch(`${API_BASE}/competitions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: newComp.name, date: newComp.date || `${raceYear}-${raceMonth}`, location: newComp.location }) })
        if (compRes.ok) {
          const cd = await compRes.json()
          compId = cd.id
          fetchCompetitions()
        }
      }

      if (!duplicateCheck) {
        const checkRes = await fetch(`${API_BASE}/check_duplicate_record`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ swimmer_name: swimmerName, stroke_type: strokeType, race_distance: raceDistance, competition_id: compId || null }),
        })
        if (checkRes.ok) {
          const checkData = await checkRes.json()
          if (checkData.duplicate) {
            setDuplicateCheck({ ...checkData, compId, metrics })
            setSaving(false)
            return
          }
        }
      }

      const res = await fetch(`${API_BASE}/manual_record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          swimmer_name: swimmerName,
          pool_length: poolLength,
          race_distance: raceDistance,
          stroke_type: strokeType,
          competition_id: compId || null,
          race_date: `${raceYear}-${raceMonth}`,
          metrics,
          linked_video_id: linkedVideoId || null,
        }),
      })
      if (res.ok) {
        resetForm()
        onSaved()
      }
    } catch {}
    setSaving(false)
  }

  const handleOverwrite = async () => {
    if (overwritePw !== 'ycz') return
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/records/${duplicateCheck.record_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          password: 'ycz',
          swimmer_name: swimmerName,
          pool_length: poolLength,
          race_distance: raceDistance,
          stroke_type: strokeType,
          competition_id: duplicateCheck.compId || null,
          race_date: `${raceYear}-${raceMonth}`,
          metrics: duplicateCheck.metrics,
        }),
      })
      if (res.ok) {
        setDuplicateCheck(null)
        setOverwritePw('')
        resetForm()
        onSaved()
      }
    } catch {}
    setSaving(false)
  }

  const S: React.CSSProperties = { padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem', width: '100%' }
  const setHalf = (key: string, val: string) => setHalfMetrics(prev => ({ ...prev, [key]: val }))

  return (
    <div className="card">
      <div className="card-title"><span className="icon">✏️</span> 手工录入记录</div>

      <div className="form-row" style={{ marginBottom: 12 }}>
        <div className="form-group">
          <label>运动员 *</label>
          <select style={S} value={swimmerName} onChange={e => setSwimmerName(e.target.value)}>
            {swimmerList.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>

      <div style={{ marginBottom: 14, padding: '10px 12px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
        <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>📷</span> 图片识别自动填充
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <label className="btn btn-sm btn-outline" style={{ cursor: 'pointer' }}>
            {recognizing ? '识别中...' : '上传图片识别'}
            <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileSelect} style={{ display: 'none' }} disabled={recognizing} />
          </label>
          {imageFile && (
            <button className="btn btn-sm btn-outline" onClick={handleReRecognize} disabled={recognizing} style={{ color: 'var(--primary)' }}>
              {recognizing ? '识别中...' : '🔄 重新识别'}
            </button>
          )}
          {recognizePreview && <img src={recognizePreview} alt="preview" onClick={() => setShowImageModal(true)} style={{ height: 40, borderRadius: 4, border: '1px solid var(--border)', cursor: 'pointer' }} />}
          {showImageModal && recognizePreview && (
            <div onClick={() => setShowImageModal(false)} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'pointer' }}>
              <img src={recognizePreview} alt="full" onClick={e => e.stopPropagation()} style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8, boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }} />
              <div onClick={() => setShowImageModal(false)} style={{ position: 'absolute', top: 16, right: 24, color: '#fff', fontSize: '1.5rem', cursor: 'pointer', userSelect: 'none' }}>✕</div>
            </div>
          )}
          {recognizeError && <span style={{ fontSize: '0.8rem', color: 'var(--danger)' }}>{recognizeError}</span>}
          {recognizing && <span style={{ fontSize: '0.8rem', color: 'var(--primary)' }}>AI识别中，请稍候...</span>}
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 4 }}>上传比赛成绩截图，AI自动识别填充表单，识别结果可手动调整</div>
      </div>

      <div className="form-row" style={{ marginBottom: 12 }}>
        <div className="form-group">
          <label>比赛 *</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <select style={{ ...S, flex: 1 }} value={selectedCompId} onChange={e => { setSelectedCompId(e.target.value); const c = competitions.find(x => x.id === e.target.value); if (c?.date) { const p = c.date.split("-"); if (p[0]) setRaceYear(p[0]); if (p[1]) setRaceMonth(p[1].padStart(2, "0")); } }}>
              <option value="">选择比赛...</option>
              {competitions.map(c => <option key={c.id} value={c.id}>{c.name}{c.date ? ` (${c.date})` : ''}</option>)}
            </select>
            <button className="btn btn-sm btn-outline" onClick={() => setShowNewComp(!showNewComp)}>{showNewComp ? '取消' : '+ 新建'}</button>
          </div>
        </div>
      </div>

      {showNewComp && (
        <div style={{ marginBottom: 12, padding: '10px 12px', background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>新建比赛</span>
            <label className="btn btn-sm btn-outline" style={{ cursor: 'pointer', fontSize: '0.8rem' }}>
              {compRecognizing ? '识别中...' : '📷 图片识别'}
              <input ref={compFileInputRef} type="file" accept="image/*" onChange={handleCompFileSelect} style={{ display: 'none' }} disabled={compRecognizing} />
            </label>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 6 }}>上传比赛通知/海报图片，AI自动识别比赛名称、日期、场馆</div>
          <div className="form-row">
            <div className="form-group"><label>比赛名称 *</label><input style={S} placeholder="如：2024年区游泳锦标赛" value={newComp.name} onChange={e => setNewComp(p => ({ ...p, name: e.target.value }))} /></div>
            <div className="form-group"><label>日期</label><input type="date" style={S} value={newComp.date} onChange={e => setNewComp(p => ({ ...p, date: e.target.value }))} /></div>
            <div className="form-group"><label>地点</label><input style={S} placeholder="如：市游泳馆" value={newComp.location} onChange={e => setNewComp(p => ({ ...p, location: e.target.value }))} /></div>
          </div>
          <button className="btn btn-sm btn-primary" onClick={handleCreateComp} disabled={creatingComp || !newComp.name}>{creatingComp ? '创建中...' : '创建比赛'}</button>
        </div>
      )}

      {recognizedComps.length > 0 && (
        <div style={{ marginBottom: 12, padding: '10px 12px', background: '#EFF6FF', borderRadius: 6, border: '1px solid #BFDBFE' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>识别到 {recognizedComps.length} 个比赛</span>
            <button className="btn btn-sm btn-primary" onClick={handleSaveAllRecognized} style={{ fontSize: '0.75rem' }}>全部保存</button>
          </div>
          {recognizedComps.map((comp, idx) => (
            <div key={idx} style={{ marginBottom: 8, padding: '8px 10px', background: '#fff', borderRadius: 6, border: '1px solid var(--border)' }}>
              <div className="form-row">
                <div className="form-group"><label>比赛名称 *</label><input style={S} value={comp.name} onChange={e => { const n = [...recognizedComps]; n[idx] = { ...n[idx], name: e.target.value }; setRecognizedComps(n) }} /></div>
                <div className="form-group"><label>日期</label><input type="date" style={S} value={comp.date} onChange={e => { const n = [...recognizedComps]; n[idx] = { ...n[idx], date: e.target.value }; setRecognizedComps(n) }} /></div>
                <div className="form-group"><label>地点</label><input style={S} value={comp.location} onChange={e => { const n = [...recognizedComps]; n[idx] = { ...n[idx], location: e.target.value }; setRecognizedComps(n) }} /></div>
              </div>
              <button className="btn btn-sm btn-primary" onClick={() => handleSaveRecognizedComp(comp)} disabled={!comp.name} style={{ fontSize: '0.75rem', marginTop: 4 }}>保存此比赛</button>
              <button className="btn btn-sm btn-outline" onClick={() => setRecognizedComps(prev => prev.filter((_, i) => i !== idx))} style={{ fontSize: '0.75rem', marginTop: 4, marginLeft: 6 }}>删除</button>
            </div>
          ))}
        </div>
      )}

      <div className="form-row" style={{ marginBottom: 12 }}>
        <div className="form-group">
          <label>比赛年月 *</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <select style={{ ...S, flex: 1 }} value={raceYear} onChange={e => setRaceYear(e.target.value)}>
              {Array.from({ length: 10 }, (_, i) => (new Date().getFullYear() - i).toString()).map(y => <option key={y} value={y}>{y}年</option>)}
            </select>
            <select style={{ ...S, flex: 1 }} value={raceMonth} onChange={e => setRaceMonth(e.target.value)}>
              {Array.from({ length: 12 }, (_, i) => (i + 1).toString().padStart(2, '0')).map(m => <option key={m} value={m}>{parseInt(m)}月</option>)}
            </select>
          </div>
        </div>
        <div className="form-group"><label>泳姿 *</label><select style={S} value={strokeType} onChange={e => setStrokeType(e.target.value)}>{STROKE_TYPES.map(s => <option key={s} value={s}>{s}</option>)}</select></div>
        <div className="form-group"><label>泳池长度</label><select style={S} value={poolLength} onChange={e => setPoolLength(parseInt(e.target.value))}><option value={50}>50米</option><option value={25}>25米</option></select></div>
        <div className="form-group"><label>比赛距离</label><select style={S} value={raceDistance} onChange={e => setRaceDistance(parseInt(e.target.value))}><option value={50}>50米</option><option value={100}>100米</option><option value={200}>200米</option><option value={400}>400米</option></select></div>
      </div>

      <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, color: 'var(--primary)' }}>各半程指标（50米/半程，共{numHalves}个半程）</div>
      {halfLabels.map((label, idx) => (
        <div key={label} style={{ marginBottom: 8, padding: '8px 10px', background: idx % 2 === 0 ? 'var(--bg)' : '#fff', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--primary)', marginBottom: 4 }}>{label}（{(idx * 50) + 50}米）</div>
          <div className="form-row">
            <div className="form-group"><label>用时 (秒)</label><input type="number" step="0.001" style={S} placeholder="必填" value={halfMetrics[`${label}用时`] || ''} onChange={e => setHalf(`${label}用时`, e.target.value)} /></div>
            <div className="form-group"><label>划水次数</label><input type="number" step="1" style={S} placeholder="选填" value={halfMetrics[`${label}划水次数`] || ''} onChange={e => setHalf(`${label}划水次数`, e.target.value)} /></div>
            <div className="form-group"><label>换气次数</label><input type="number" step="1" style={S} placeholder="选填" value={halfMetrics[`${label}换气次数`] || ''} onChange={e => setHalf(`${label}换气次数`, e.target.value)} /></div>
            <div className="form-group"><label>打腿次数</label><input type="number" step="1" style={S} placeholder="选填" value={halfMetrics[`${label}打腿次数`] || ''} onChange={e => setHalf(`${label}打腿次数`, e.target.value)} /></div>
          </div>
        </div>
      ))}

      <div className="form-row" style={{ marginBottom: 12 }}>
        <div className="form-group"><label style={{ fontWeight: 600, color: 'var(--primary)' }}>比赛总用时 (秒) *</label><input type="number" step="0.001" style={{ ...S, fontWeight: 600 }} placeholder="必填" value={totalTime} onChange={e => setTotalTime(e.target.value)} /></div>
      </div>

      <div className="form-group" style={{ marginBottom: 14 }}>
        <label>关联视频</label>
        <select style={S} value={linkedVideoId} onChange={e => setLinkedVideoId(e.target.value)}>
          <option value="">不关联</option>
          {videos.map((v: any) => <option key={v.id} value={v.id}>{v.display_name || v.file_name}</option>)}
        </select>
      </div>
      <button className="btn btn-primary" onClick={handleSave} disabled={saving}>{saving ? '提交中...' : '提交'}</button>

      {duplicateCheck && (
        <div onClick={() => { setDuplicateCheck(null); setOverwritePw('') }} style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 20, maxWidth: 400, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
            <div style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 12 }}>⚠️ 发现重复记录</div>
            <div style={{ fontSize: '0.85rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
              已存在相同记录：{duplicateCheck.swimmer_name} · {duplicateCheck.race_name || '未命名'} · {duplicateCheck.stroke_type} · {duplicateCheck.race_distance}米
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 4, display: 'block' }}>输入密码以覆盖</label>
              <input type="password" value={overwritePw} onChange={e => setOverwritePw(e.target.value)} style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: '0.85rem' }} placeholder="请输入密码" />
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={() => { setDuplicateCheck(null); setOverwritePw('') }}>取消</button>
              <button className="btn btn-primary" onClick={handleOverwrite} disabled={saving || overwritePw !== 'ycz'}>{saving ? '覆盖中...' : '确认覆盖'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
