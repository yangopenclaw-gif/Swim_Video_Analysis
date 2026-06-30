import React, { useState, useEffect, useRef } from 'react'
import { VideoUploader } from './uploader'

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
}

type TabType = '杨钧涵' | '杨涴婷' | '对比分析'
type UploadPhase = 'idle' | 'uploading' | 'uploaded' | 'analyzing' | 'completed' | 'failed'

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('杨钧涵')
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


  useEffect(() => {
    const pending = VideoUploader.getPendingUploads()
    if (pending.length > 0) {
      setPendingUploads(pending)
    }
  }, [])

  useEffect(() => {
    if (activeTab === '杨钧涵' || activeTab === '杨涴婷') {
      setSwimmerName(activeTab)
      fetchRecords(activeTab)
    } else {
      fetchAllRecords()
    }
  }, [activeTab])

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

  const handleDeleteRecord = async (id: string) => {
    if (!confirm('确定删除此归档记录？')) return
    try { await fetch(`${API_BASE}/records/${id}`, { method: 'DELETE' }); fetchRecords(swimmerName); fetchAllRecords() } catch {}
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

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(2)}秒`
    const m = Math.floor(seconds / 60); const s = seconds % 60
    return `${m}分${s.toFixed(2)}秒`
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

  const renderRecords = () => (
    <div className="card">
      <div className="card-title"><span className="icon">📋</span> 历史归档记录</div>
      {records.length === 0 ? (
        <div className="empty-state">
          <div className="icon">📭</div>
          <p>暂无归档记录</p>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 4 }}>
            上传视频并分析归档后，记录将显示在此处
          </p>
        </div>
      ) : (
        <div className="records-list">
          {records.map(r => (
            <div key={r.id} className="record-item">
              <div className="record-info">
                <span className="name">
                  {r.race_name || '未命名比赛'}
                  <span className="badge badge-blue" style={{ marginLeft: 8 }}>
                    {r.pool_length}米池 / {r.race_distance}米{r.stroke_type}
                  </span>
                </span>
                <span className="meta">
                  {r.race_date || '未设置日期'} {r.race_location ? `· ${r.race_location}` : ''}
                  {r.archive_time ? ` · 归档于 ${new Date(r.archive_time).toLocaleDateString()}` : ''}
                </span>
              </div>
              <div className="record-actions">
                <button
                  className="btn btn-sm btn-outline"
                  onClick={() => {
                    setTaskId(r.id)
                    setAnalysisResult(r.analysis_result)
                    setUploadPhase('completed')
                  }}
                >
                  查看详情
                </button>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => handleDeleteRecord(r.id)}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

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

  const renderSwimmerPage = () => (
    <>
      {renderUploadSection()}
      {renderAnalysisOptions()}
      {renderResult()}
      {renderRecords()}
      {renderVideoManager()}
      {renderArchiveModal()}
      {renderAnalyzeVideoModal()}
    </>
  )

  const renderComparePage = () => (
    <>
      <div className="card">
        <div className="card-title"><span className="icon">⚖️</span> 对比分析</div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 16 }}>
          选择两场同类型比赛的分析记录进行对比
        </p>

      <div className="form-row">
          <div className="form-group">
            <label>比赛记录 1</label>
            <select value={compareId1} onChange={e => setCompareId1(e.target.value)}>
              <option value="">请选择</option>
              {allRecords.map(r => (
                <option key={r.id} value={r.id}>
                  {r.swimmer_name} - {r.race_name || '未命名'} ({r.pool_length}m池/{r.race_distance}m)
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>比赛记录 2</label>
            <select value={compareId2} onChange={e => setCompareId2(e.target.value)}>
              <option value="">请选择</option>
              {allRecords.map(r => (
                <option key={r.id} value={r.id}>
                  {r.swimmer_name} - {r.race_name || '未命名'} ({r.pool_length}m池/{r.race_distance}m)
                </option>
              ))}
            </select>
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleCompare} disabled={!compareId1 || !compareId2}>
          开始对比
        </button>
      </div>

      {compareData && (
        <div className="card">
          <div className="card-title"><span className="icon">📊</span> 对比结果</div>
          <div className="compare-container">
            {['record1', 'record2'].map((key, idx) => {
              const rec = compareData[key]
              const panelClass = idx === 0 ? 'left' : 'right'
              const color = idx === 0 ? '🔵' : '🟢'
              return (
                <div key={key} className={`compare-panel ${panelClass}`}>
                  <h3>
                    {color} {rec.swimmer_name} - {rec.race_name || '未命名'}
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 12 }}>
                    {rec.pool_length}米池 / {rec.race_distance}米自由泳
                    {rec.race_date ? ` · ${rec.race_date}` : ''}
                  </p>
                  <table className="compare-table">
                    <thead>
                      <tr>
                        <th>指标</th>
                        <th>数值</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(rec.analysis_result).map(([k, v]: [string, any]) => (
                        <tr key={k}>
                          <td>{k}</td>
                          <td><strong>{v.value}</strong> <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>{v.unit}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            })}
          </div>

          {compareData.record1.analysis_result && compareData.record2.analysis_result && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ marginBottom: 12, fontSize: '1rem' }}>📈 差异对比</h3>
              <table className="result-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>记录1</th>
                    <th>记录2</th>
                    <th>差异</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const r1 = compareData.record1.analysis_result
                    const r2 = compareData.record2.analysis_result
                    const allKeys = new Set([...Object.keys(r1), ...Object.keys(r2)])
                    return Array.from(allKeys).map(key => {
                      const v1 = r1[key]?.value
                      const v2 = r2[key]?.value
                      const n1 = typeof v1 === 'number' ? v1 : parseFloat(v1 as string)
                      const n2 = typeof v2 === 'number' ? v2 : parseFloat(v2 as string)
                      const diff = !isNaN(n1) && !isNaN(n2) ? n2 - n1 : null
                      const unit = r1[key]?.unit || r2[key]?.unit || ''
                      return (
                        <tr key={key}>
                          <td>{key}</td>
                          <td>{v1 ?? '-'} <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{unit}</span></td>
                          <td>{v2 ?? '-'} <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{unit}</span></td>
                          <td>
                            {diff !== null ? (
                              <span className={diff > 0 ? 'diff-positive' : diff < 0 ? 'diff-negative' : ''}>
                                {diff > 0 ? '+' : ''}{diff.toFixed(3)}
                              </span>
                            ) : '-'}
                          </td>
                        </tr>
                      )
                    })
                  })()}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  )

  return (
    <div>
      <header className="header">
        <div className="header-inner">
          <div>
            <h1>🏊 游泳比赛视频分析系统</h1>
            <div className="subtitle">基于 MediaPipe PoseLandmarker 的智能运动分析 · 分片断点续传</div>
          </div>
          <div className="tabs">
            {(['杨钧涵', '杨涴婷', '对比分析'] as TabType[]).map(tab => (
              <button
                key={tab}
                className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </header>
      <main className="main">
        <div className="container">
          {activeTab === '对比分析' ? renderComparePage() : renderSwimmerPage()}
        </div>
      </main>
    </div>
  )
}

export default App
