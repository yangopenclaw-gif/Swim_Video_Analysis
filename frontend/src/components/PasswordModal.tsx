import React, { useState, useEffect, useRef } from 'react'

interface PasswordModalProps {
  open: boolean
  onConfirm: (password: string) => void
  onCancel: () => void
  error?: string
}

export const PasswordModal: React.FC<PasswordModalProps> = ({ open, onConfirm, onCancel, error }) => {
  const [password, setPassword] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (open) {
      setPassword('')
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  if (!open) return null

  return (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: '#fff', borderRadius: 8, padding: 24, minWidth: 320, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
        <h3 style={{ margin: '0 0 12px 0' }}>密码验证</h3>
        <p style={{ fontSize: 14, color: '#666', margin: '0 0 12px 0' }}>该记录已归档，请输入密码以继续操作</p>
        <input
          ref={inputRef}
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && password) onConfirm(password) }}
          placeholder="请输入归档密码"
          style={{ width: '100%', padding: '8px 12px', fontSize: 14, boxSizing: 'border-box', border: '1px solid #d9d9d9', borderRadius: 4 }}
        />
        {error && <p style={{ color: '#ff4d4f', fontSize: 12, margin: '4px 0 0 0' }}>{error}</p>}
        <div style={{ marginTop: 16, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={{ padding: '6px 16px', cursor: 'pointer' }}>取消</button>
          <button onClick={() => { if (password) onConfirm(password) }} style={{ padding: '6px 16px', cursor: 'pointer', background: '#1890ff', color: '#fff', border: 'none', borderRadius: 4 }}>确认</button>
        </div>
      </div>
    </div>
  )
}