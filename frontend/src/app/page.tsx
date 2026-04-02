'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'

const API = 'http://localhost:8000'
const PROVIDERS = [
  { id: 'claude', label: 'Claude',     sub: 'Anthropic',   icon: '◆' },
  { id: 'openai', label: 'OpenAI',     sub: 'GPT-4o',      icon: '○' },
  { id: 'local',  label: 'Local vLLM', sub: 'Self-hosted', icon: '◎' },
]

export default function Home() {
  const router = useRouter()
  const [provider,    setProvider]    = useState('local')
  const [apiKey,      setApiKey]      = useState('')
  const [serverUrl,   setServerUrl]   = useState('')
  const [modelName,   setModelName]   = useState('')
  const [hasKey,      setHasKey]      = useState(false)
  const [datasetPath, setDatasetPath] = useState('')
  const [datasetName, setDatasetName] = useState('')
  const [task,        setTask]        = useState('')
  const [launching,   setLaunching]   = useState(false)
  const [errors,      setErrors]      = useState<string[]>([])
  const [showCreds,   setShowCreds]   = useState(false)
  const [ovKey,       setOvKey]       = useState('')
  const runIdRef  = useRef('')
  const canNavRef = useRef(false)

  const tryNavigate = useCallback(() => {
    if (runIdRef.current && canNavRef.current) router.push(`/run/${runIdRef.current}`)
  }, [router])

  useEffect(() => {
    fetch(`${API}/api/creds`).then(r => r.json()).then(d => {
      setProvider(d.provider ?? 'local'); setHasKey(d.hasKey)
      setServerUrl(d.serverUrl ?? ''); setModelName(d.model ?? '')
    }).catch(() => {})
  }, [])

  const browse = async (dir: boolean) => {
    try {
      const r = await fetch(`${API}/api/browse?dir=${dir}`)
      const d = await r.json()
      if (d.path) { setDatasetPath(d.path); setDatasetName(d.path.split('/').pop() ?? d.path) }
    } catch { setErrors(['Cannot reach server. Run: python server.py']) }
  }

  const saveCreds = async () => {
    await fetch(`${API}/api/creds`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: ovKey, server_url: serverUrl, model: modelName }) })
    setHasKey(!!ovKey); setShowCreds(false)
  }

  const launch = async () => {
    const errs: string[] = []
    if (!datasetPath)                               errs.push('Select a dataset first.')
    if (provider !== 'local' && !apiKey && !hasKey) errs.push('API key is required.')
    if (provider === 'local' && !serverUrl)          errs.push('vLLM server URL is required.')
    if (provider === 'local' && !modelName)          errs.push('Model name is required.')
    if (errs.length) { setErrors(errs); return }
    setErrors([]); setLaunching(true)
    try {
      if (provider === 'local' || apiKey) {
        await fetch(`${API}/api/creds`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider, api_key: apiKey, server_url: serverUrl, model: modelName }) })
      }
      const r = await fetch(`${API}/api/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, api_key: apiKey, server_url: serverUrl, model: modelName, dataset_path: datasetPath, task_description: task }) })
      const d = await r.json()
      if (d.runId) { runIdRef.current = d.runId; canNavRef.current = true; tryNavigate() }
      else { setLaunching(false); setErrors([d.detail ?? 'Failed to start.']) }
    } catch { setLaunching(false); setErrors(['Cannot reach server at localhost:8000']) }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>

      {/* Nav — floating glass strip */}
      <motion.nav
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        style={{
          position: 'fixed', top: 20, left: '50%', transform: 'translateX(-50%)',
          zIndex: 50, width: 'calc(100% - 64px)', maxWidth: 960,
          background: 'rgba(8,2,2,0.65)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 14,
          padding: '12px 20px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 26, height: 26, borderRadius: 7, background: 'linear-gradient(135deg,#e63030,#7a0000)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: '#fff', fontWeight: 700 }}>◆</div>
          <span style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 600, fontSize: 14 }}>DS Agent Team</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-ghost" onClick={() => setShowCreds(v => !v)} style={{ fontSize: 11.5, padding: '6px 12px' }}>⚙ Credentials</button>
        </div>
      </motion.nav>

      {/* Hero */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '100px 32px 60px', gap: 48 }}>

        {/* Left — floating text (no background) */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          style={{ flex: 1, maxWidth: 420 }}
        >
          <div className="tag tag-red" style={{ marginBottom: 22, width: 'fit-content' }}>Multi-Agent Analysis</div>
          <h1 style={{
            fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700,
            fontSize: 'clamp(36px,4.5vw,58px)', lineHeight: 1.05,
            letterSpacing: '-0.03em', marginBottom: 20,
          }}>
            Analyse any<br />
            <span style={{ color: '#e63030' }}>dataset.</span>
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.32)', fontSize: 14.5, lineHeight: 1.75, marginBottom: 36 }}>
            A team of specialised AI agents explores your data, identifies patterns, and builds a complete analysis plan — autonomously.
          </p>

          {/* Agent chips — floating, no card */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {[
              { label: 'Explorer',       color: '#7c6fcd' },
              { label: 'Skeptic',        color: '#d46b8a' },
              { label: 'Statistician',   color: '#4a9fd4' },
              { label: 'Ethicist',       color: '#d4874a' },
              { label: 'Feature Eng.',   color: '#3db87a' },
              { label: 'Pragmatist',     color: '#c4a832' },
              { label: 'Devil Adv.',     color: '#e63030' },
              { label: 'Optimizer',      color: '#8a7cd4' },
            ].map((a, i) => (
              <motion.span
                key={a.label}
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 + i * 0.04 }}
                style={{
                  padding: '4px 11px', borderRadius: 7,
                  background: `${a.color}0f`,
                  border: `1px solid ${a.color}28`,
                  color: `${a.color}cc`,
                  fontSize: 10.5, fontFamily: "'JetBrains Mono',monospace",
                  backdropFilter: 'blur(6px)',
                }}
              >
                {a.label}
              </motion.span>
            ))}
          </div>
        </motion.div>

        {/* Right — glass form broken into sections */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          style={{ flex: 1, maxWidth: 400, display: 'flex', flexDirection: 'column', gap: 12 }}
        >

          {/* Credentials drawer */}
          <AnimatePresence>
            {showCreds && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
                <div style={{ background: 'rgba(8,2,2,0.7)', backdropFilter: 'blur(20px)', border: '1px solid rgba(230,48,48,0.2)', borderRadius: 14, padding: 16, display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 4 }}>
                  <div className="label">Override API Key</div>
                  <input className="field" type="password" placeholder="Paste new key…" value={ovKey} onChange={e => setOvKey(e.target.value)} />
                  <button className="btn" style={{ padding: '9px 16px', fontSize: 12.5 }} onClick={saveCreds}>Save</button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Provider — standalone floating section */}
          <div style={{ background: 'rgba(8,2,2,0.55)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '16px 18px' }}>
            <div className="label" style={{ marginBottom: 10 }}>Provider</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
              {PROVIDERS.map(p => (
                <button key={p.id} onClick={() => setProvider(p.id)} style={{
                  padding: '10px 6px', borderRadius: 10, cursor: 'pointer', textAlign: 'center',
                  background: provider === p.id ? 'rgba(230,48,48,0.12)' : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${provider === p.id ? 'rgba(230,48,48,0.4)' : 'rgba(255,255,255,0.06)'}`,
                  color: provider === p.id ? '#e63030' : 'rgba(255,255,255,0.28)',
                  transition: 'all 0.18s',
                  backdropFilter: 'blur(8px)',
                }}>
                  <div style={{ fontSize: 15, marginBottom: 4 }}>{p.icon}</div>
                  <div style={{ fontSize: 11, fontWeight: 600 }}>{p.label}</div>
                  <div style={{ fontSize: 9.5, opacity: 0.45, marginTop: 1 }}>{p.sub}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Auth — standalone floating section */}
          <div style={{ background: 'rgba(8,2,2,0.55)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '16px 18px' }}>
            {provider === 'local' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div className="label" style={{ marginBottom: 2 }}>Server Config</div>
                <input className="field" placeholder="http://localhost:8001/v1" value={serverUrl} onChange={e => setServerUrl(e.target.value)} />
                <input className="field" placeholder="Model name" value={modelName} onChange={e => setModelName(e.target.value)} />
              </div>
            ) : (
              <>
                <div className="label" style={{ marginBottom: 8 }}>API Key</div>
                <div style={{ position: 'relative' }}>
                  <input className="field" type="password" placeholder={provider === 'claude' ? 'sk-ant-…' : 'sk-…'} value={apiKey} onChange={e => setApiKey(e.target.value)} style={{ paddingRight: hasKey && !apiKey ? 72 : 14 }} />
                  {hasKey && !apiKey && <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 10.5, color: '#34d399', fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>✓ saved</span>}
                </div>
              </>
            )}
          </div>

          {/* Dataset — standalone floating section */}
          <div style={{ background: 'rgba(8,2,2,0.55)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '16px 18px' }}>
            <div className="label" style={{ marginBottom: 10 }}>Dataset</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <button className="btn-ghost" onClick={() => browse(false)}>📄 File</button>
              <button className="btn-ghost" onClick={() => browse(true)}>📁 Folder</button>
            </div>
            <AnimatePresence>
              {datasetPath && (
                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  style={{ marginTop: 10, padding: '7px 12px', borderRadius: 8, background: 'rgba(52,211,153,0.07)', border: '1px solid rgba(52,211,153,0.18)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#34d399', fontSize: 11 }}>✓</span>
                  <span style={{ fontSize: 11.5, color: 'rgba(52,211,153,0.8)', fontFamily: "'JetBrains Mono',monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{datasetName}</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Goal — standalone floating section */}
          <div style={{ background: 'rgba(8,2,2,0.55)', backdropFilter: 'blur(20px)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, padding: '16px 18px' }}>
            <div className="label" style={{ marginBottom: 8 }}>Goal <span style={{ textTransform: 'none', fontSize: 10, color: 'rgba(255,255,255,0.15)', letterSpacing: 0 }}>— optional</span></div>
            <textarea className="field" rows={2} placeholder="e.g. Predict churn. Metric: AUC." value={task} onChange={e => setTask(e.target.value)} style={{ resize: 'none', lineHeight: 1.55 }} />
          </div>

          {/* Errors */}
          <AnimatePresence>
            {errors.length > 0 && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(230,48,48,0.07)', border: '1px solid rgba(230,48,48,0.22)', backdropFilter: 'blur(8px)' }}>
                {errors.map((e, i) => <p key={i} style={{ fontSize: 12.5, color: '#f87171' }}>✕ {e}</p>)}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Launch */}
          <motion.button className="btn" onClick={launch} disabled={launching} whileTap={{ scale: 0.98 }}
            style={{ padding: '14px 20px', fontSize: 14, fontWeight: 600, letterSpacing: '0.02em' }}>
            {launching ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                <span style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.25)', borderTopColor: '#fff', display: 'inline-block' }} className="spin-slow" />
                Launching…
              </span>
            ) : 'Launch Analysis →'}
          </motion.button>
        </motion.div>
      </div>

      {/* Floating footer */}
      <div style={{ padding: '16px 32px', display: 'flex', justifyContent: 'space-between' }}>
        <span className="mono" style={{ fontSize: 10 }}>DS-AGENT-TEAM v2.0</span>
        <span className="mono" style={{ fontSize: 10 }}>localhost:8000</span>
      </div>
    </div>
  )
}
