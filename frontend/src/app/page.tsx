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

const WORKFLOW_STEPS = [
  { num: '01', title: 'Data Discovery',   desc: 'Auto-detect format, profile structure & quality' },
  { num: '02', title: 'Understanding',    desc: 'Explorer, Skeptic & Statistician analyse patterns' },
  { num: '03', title: 'Model Design',     desc: 'Feature engineering, architecture & optimization' },
  { num: '04', title: 'Code Generation',  desc: 'Autonomous code writing with retry & diagnostics' },
  { num: '05', title: 'Final Report',     desc: 'Synthesised insights and actionable recommendations' },
]

const AGENTS = [
  { label: 'Explorer',       icon: '◉', color: '#38bdf8', role: 'Data Scout' },
  { label: 'Skeptic',        icon: '⚠', color: '#fb7185', role: 'Quality Guard' },
  { label: 'Statistician',   icon: '∑', color: '#3b82f6', role: 'Numbers Expert' },
  { label: 'Feature Eng.',   icon: '⟁', color: '#818cf8', role: 'Signal Extractor' },
  { label: 'Ethicist',       icon: '⚖', color: '#34d399', role: 'Bias Detector' },
  { label: 'Pragmatist',     icon: '◈', color: '#fbbf24', role: 'Reality Check' },
  { label: 'Devil Adv.',     icon: '⛧', color: '#f97316', role: 'Critical Thinker' },
  { label: 'Optimizer',      icon: '⚡', color: '#2dd4bf', role: 'Efficiency Expert' },
  { label: 'Architect',      icon: '⬡', color: '#c084fc', role: 'System Designer' },
  { label: 'Final Report',   icon: '◎', color: '#f0c040', role: 'Pipeline Output' },
]

// Typewriter hook
function useTypewriter(text: string, speed = 60, delay = 800) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)
  useEffect(() => {
    setDisplayed(''); setDone(false)
    const timeout = setTimeout(() => {
      let i = 0
      const interval = setInterval(() => {
        setDisplayed(text.slice(0, i + 1))
        i++
        if (i >= text.length) { clearInterval(interval); setDone(true) }
      }, speed)
      return () => clearInterval(interval)
    }, delay)
    return () => clearTimeout(timeout)
  }, [text, speed, delay])
  return { displayed, done }
}

// All 20 persona handles — auto-used in Red Mode, no selection needed
const ALL_PERSONA_HANDLES = [
  'andrej_karpathy','yann_lecun','sam_altman','geoffrey_hinton','francois_chollet',
  'andrew_ng','chip_huyen','jeremy_howard','chris_olah','edward_yang',
  'ethan_mollick','jay_alammar','jonas_mueller','lilian_weng','matei_zaharia',
  'santiago_valdarrama','sebastian_raschka','shreya_rajpal','tim_dettmers','vicki_boykis',
]

export default function Home() {
  const router = useRouter()
  const [provider,    setProvider]    = useState('local')
  const [apiKey,      setApiKey]      = useState('')
  const [serverUrl,   setServerUrl]   = useState('')
  const [modelName,   setModelName]   = useState('')
  const [hasKey,      setHasKey]      = useState(false)
  const [datasetPath,    setDatasetPath]    = useState('')
  const [datasetName,    setDatasetName]    = useState('')
  const [task,        setTask]        = useState('')
  const [launching,   setLaunching]   = useState(false)
  const [testMode,    setTestMode]    = useState(false)
  const [errors,      setErrors]      = useState<string[]>([])
  const [showCreds,   setShowCreds]   = useState(false)
  const [ovKey,       setOvKey]       = useState('')
  // ── Red Mode state ────────────────────────────────────────────────
  const [isRedMode, setIsRedMode] = useState(false)
  const runIdRef     = useRef('')
  const canNavRef    = useRef(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dirInputRef  = useRef<HTMLInputElement>(null)

  // Hydrate mode state so pressing 'back' doesn't switch to Phase 1 randomly
  useEffect(() => {
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('redMode') === 'true') {
      setIsRedMode(true)
    }
  }, [])

  const tagline = useTypewriter(
    isRedMode ? '20 real experts debate your analysis' : 'Autonomous multi-agent data science pipeline',
    45, 600
  )

  const tryNavigate = useCallback(() => {
    if (runIdRef.current && canNavRef.current) {
      router.push(isRedMode ? `/red/${runIdRef.current}` : `/run/${runIdRef.current}`)
    }
  }, [router, isRedMode])

  useEffect(() => {
    fetch(`${API}/api/creds`).then(r => r.json()).then(d => {
      setProvider(d.provider ?? 'local'); setHasKey(d.hasKey)
      setServerUrl(d.serverUrl ?? ''); setModelName(d.model ?? '')
    }).catch(() => {})
  }, [])

  // Sync mode with global background
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('setAppMode', { detail: isRedMode ? 'red' : 'blue' }))
  }, [isRedMode])



  const pickPath = async (e: React.ChangeEvent<HTMLInputElement>, isDir: boolean) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    const f = files[0]
    // Some environments (Electron / Tauri) expose the real path directly
    const nativePath = (f as File & { path?: string }).path
    if (nativePath) {
      const p = isDir ? nativePath.substring(0, nativePath.lastIndexOf('/') || nativePath.lastIndexOf('\\')) : nativePath
      setDatasetPath(p); setDatasetName(p.split(/[/\\]/).filter(Boolean).pop() ?? p)
      e.target.value = ''; return
    }
    // Browser — no absolute path available. Ask server to resolve by filename.
    const rel = isDir ? (f.webkitRelativePath || f.name) : f.name
    try {
      const r = await fetch(`${API}/api/resolve?name=${encodeURIComponent(rel)}&dir=${isDir}`)
      const d = await r.json()
      if (d.path) { setDatasetPath(d.path); setDatasetName(d.name ?? rel) }
      else { setDatasetPath(rel); setDatasetName(rel.split(/[/\\]/).filter(Boolean).pop() ?? rel) }
    } catch {
      setDatasetPath(rel); setDatasetName(rel.split(/[/\\]/).filter(Boolean).pop() ?? rel)
    }
    e.target.value = ''
  }

  const saveCreds = async () => {
    await fetch(`${API}/api/creds`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: ovKey, server_url: serverUrl, model: modelName }) })
    setHasKey(!!ovKey); setShowCreds(false)
  }

  const launch = async () => {
    if (testMode) {
      const mockId = `test-${Math.random().toString(36).slice(2, 8)}`
      router.push(isRedMode ? `/red/${mockId}` : `/run/${mockId}`)
      return
    }

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

      const endpoint = isRedMode ? `${API}/api/red-mode` : `${API}/api/run`
      const allPersonaHandles = ALL_PERSONA_HANDLES
      const body = isRedMode
        ? { provider, api_key: apiKey, server_url: serverUrl, model: modelName,
            dataset_path: datasetPath, task_description: task,
            persona_names: allPersonaHandles }
        : { provider, api_key: apiKey, server_url: serverUrl, model: modelName,
            dataset_path: datasetPath, task_description: task }

      const r = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body) })
      const d = await r.json()
      if (d.runId) { runIdRef.current = d.runId; canNavRef.current = true; tryNavigate() }
      else { setLaunching(false); setErrors([d.detail ?? 'Failed to start.']) }
    } catch { setLaunching(false); setErrors(['Cannot reach server at localhost:8000']) }
  }

  const accentColor = isRedMode ? '#e11d48' : '#ffffff'
  const accentRgb   = isRedMode ? '225,29,72' : '255,255,255'

  return (
    <>
      {/* Red Mode overlay — smooth colour tint during canvas transition */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none',
        background: isRedMode ? 'rgba(5,0,0,0.5)' : 'transparent',
        transition: 'background 1.1s cubic-bezier(0.4,0,0.2,1)',
      }} />
    <div data-mode={isRedMode ? 'red' : 'blue'} style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>

      {/* Main content — 3-column layout */}
      <div style={{ flex: 1, display: 'flex', paddingTop: 90, paddingBottom: 40, gap: 24, maxWidth: 1200, margin: '0 auto', width: '100%', padding: '40px 32px' }}>

        {/* CENTER — Hero + tagline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.05 }}
          style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', minWidth: 0 }}
        >
          {/* Tagline with typewriter */}
          <div style={{ marginBottom: 24 }}>
            <span className="tag" style={{
              fontSize: 10, letterSpacing: '0.1em',
              background: `rgba(${accentRgb},0.1)`,
              border:     `1px solid rgba(${accentRgb},0.25)`,
              color:      accentColor,
              transition: 'all 0.6s ease',
            }}>
              {tagline.displayed}
              <span style={{ display: 'inline-block', width: 1, height: '0.85em', background: accentColor, marginLeft: 1, verticalAlign: 'text-bottom', animation: 'blink-cursor 0.9s step-end infinite' }} />
            </span>
          </div>

          <h1 style={{
            fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700,
            fontSize: 'clamp(40px,5vw,64px)', lineHeight: 1.0,
            letterSpacing: '-0.04em', marginBottom: 20,
            transition: 'all 0.6s ease',
          }}>
            <span className="gradient-text">{isRedMode ? 'Debate any' : 'Analyse any'}</span><br />
            <span style={{ color: isRedMode ? '#e11d48' : '#ffffff', transition: 'color 0.6s ease' }}>
              {isRedMode ? 'analysis.' : 'dataset.'}
            </span>
          </h1>

          <p style={{ color: 'rgba(255,255,255,0.28)', fontSize: 14.5, lineHeight: 1.75, maxWidth: 420, marginBottom: 40, transition: 'all 0.4s ease' }}>
            {isRedMode
              ? '20 real AI experts — Karpathy, LeCun, Hinton, Chollet and more — debate your analysis in 3 rounds and synthesise a verdict.'
              : 'A team of 10 specialised AI agents explores your data, identifies patterns, builds models, and generates complete analysis — autonomously, with zero human intervention.'}
          </p>

          {/* Scroll indicator */}
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            style={{ color: 'rgba(255,255,255,0.12)', fontSize: 22, cursor: 'default' }}
          >
            ↓
          </motion.div>
        </motion.div>

        {/* RIGHT COLUMN — Console-style upload + config */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
          style={{ width: 360, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          {/* Top controls */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            {/* Red Mode toggle */}
            <motion.button
              onClick={() => {
                setIsRedMode(v => {
                  const n = !v
                  if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('redMode', String(n))
                  return n
                })
                setErrors([])
              }}
              whileTap={{ scale: 0.95 }}
              style={{
                fontSize: 11, padding: '5px 14px', borderRadius: 8, cursor: 'pointer',
                fontFamily: "'JetBrains Mono',monospace", fontWeight: 700, letterSpacing: '0.04em',
                background: isRedMode ? 'rgba(225,29,72,0.1)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${isRedMode ? 'rgba(225,29,72,0.4)' : 'rgba(255,255,255,0.1)'}`,
                color: isRedMode ? '#e11d48' : 'rgba(255,255,255,0.4)',
                boxShadow: isRedMode ? '0 0 16px rgba(225,29,72,0.3)' : 'none',
                transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
              }}
            >
              red mode
            </motion.button>
            <button
              onClick={() => setTestMode(v => !v)}
              style={{
                fontSize: 11, padding: '5px 12px', borderRadius: 8, cursor: 'pointer', fontFamily: "'JetBrains Mono',monospace",
                background: testMode ? `rgba(${accentRgb},0.12)` : 'rgba(255,255,255,0.04)',
                border: `1px solid ${testMode ? `rgba(${accentRgb},0.4)` : 'rgba(255,255,255,0.1)'}`,
                color: testMode ? accentColor : 'rgba(255,255,255,0.35)',
                boxShadow: testMode ? `0 0 16px rgba(${accentRgb},0.2)` : 'none',
                transition: 'all 0.18s',
              }}
            >
              {testMode ? '✓ test mode' : '⊘ test mode'}
            </button>
            <button className="btn-ghost" onClick={() => setShowCreds(v => !v)} style={{ fontSize: 11, padding: '5px 12px' }}>⚙ Credentials</button>
          </div>

          {/* Credentials drawer */}
          <AnimatePresence>
            {showCreds && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} style={{ overflow: 'hidden' }}>
                <div style={{ background: 'rgba(10,10,10,0.8)', border: `1px solid rgba(${accentRgb},0.15)`, borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 4 }}>
                  <div className="label">Override API Key</div>
                  <input className="field" type="password" placeholder="Paste new key…" value={ovKey} onChange={e => setOvKey(e.target.value)} />
                  <button className="btn" style={{ padding: '9px 16px', fontSize: 12.5 }} onClick={saveCreds}>Save</button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Provider */}
          <div style={{ background: 'rgba(10,10,10,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: '16px 18px' }}>
            <div className="label" style={{ marginBottom: 10 }}>Provider</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
              {PROVIDERS.map(p => (
                <button key={p.id} onClick={() => setProvider(p.id)} style={{
                  padding: '10px 6px', borderRadius: 10, cursor: 'pointer', textAlign: 'center',
                  background: provider === p.id ? `rgba(${accentRgb},0.12)` : 'rgba(255,255,255,0.02)',
                  border: `1px solid ${provider === p.id ? `rgba(${accentRgb},0.4)` : 'rgba(255,255,255,0.06)'}`,
                  color: provider === p.id ? accentColor : 'rgba(255,255,255,0.28)',
                  boxShadow: provider === p.id ? `0 0 16px rgba(${accentRgb},0.2)` : 'none',
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

          {/* Auth */}
          <div style={{ background: 'rgba(10,10,10,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: '16px 18px' }}>
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
                  {hasKey && !apiKey && <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 10.5, color: accentColor, fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>✓ saved</span>}
                </div>
              </>
            )}
          </div>

          {/* Dataset */}
          <div className="console-box" style={{ padding: '18px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.15)', fontFamily: "'JetBrains Mono',monospace" }}>$</span>
              <div className="label">Dataset</div>
            </div>

            {/* Pick buttons */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
              <button className="btn-ghost" onClick={() => fileInputRef.current?.click()}
                style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11 }}>⊞ file</button>
              <button className="btn-ghost" onClick={() => dirInputRef.current?.click()}
                style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11 }}>⊟ folder</button>
            </div>

            {/* Hidden browser-native pickers — no upload, just metadata */}
            <input ref={fileInputRef} type="file"
              accept=".csv,.tsv,.parquet,.feather,.json,.jsonl,.xlsx,.xls,.h5,.zip,.tar,.gz"
              style={{ display: 'none' }} onChange={e => pickPath(e, false)} />
            <input ref={dirInputRef} type="file"
              // @ts-expect-error non-standard but widely supported
              webkitdirectory="true" multiple style={{ display: 'none' }}
              onChange={e => pickPath(e, true)} />

            {/* Manual path override */}
            <input className="field"
              placeholder="or paste full path here…"
              value={datasetPath}
              onChange={e => { setDatasetPath(e.target.value); setDatasetName(e.target.value.split(/[/\\]/).filter(Boolean).pop() ?? '') }}
              style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11 }}
            />

            <AnimatePresence>
              {datasetName && (
                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  style={{ marginTop: 8, padding: '7px 12px', borderRadius: 8, background: `rgba(${accentRgb},0.07)`, border: `1px solid rgba(${accentRgb},0.25)`, display: 'flex', alignItems: 'center', gap: 8, boxShadow: `0 0 12px rgba(${accentRgb},0.15)` }}>
                  <span style={{ color: accentColor, fontSize: 11 }}>✓</span>
                  <span style={{ fontSize: 11, color: `rgba(${accentRgb},0.8)`, fontFamily: "'JetBrains Mono',monospace", overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{datasetPath}</span>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Goal */}
          <div style={{ background: 'rgba(10,10,10,0.6)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.15)', fontFamily: "'JetBrains Mono',monospace" }}>&gt;</span>
              <div className="label">Task Description <span style={{ textTransform: 'none', fontSize: 10, color: 'rgba(255,255,255,0.15)', letterSpacing: 0 }}>— optional</span></div>
            </div>
            <textarea className="field" rows={2} placeholder="e.g. Predict churn. Metric: AUC." value={task} onChange={e => setTask(e.target.value)} style={{ resize: 'none', lineHeight: 1.55, fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }} />
          </div>

          {/* Errors */}
          <AnimatePresence>
            {errors.length > 0 && (
              <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                style={{ padding: '10px 14px', borderRadius: 10, background: `rgba(${accentRgb},0.07)`, border: `1px solid rgba(${accentRgb},0.22)`, backdropFilter: 'blur(8px)' }}>
                {errors.map((e, i) => <p key={i} style={{ fontSize: 12.5, color: '#f87171' }}>✕ {e}</p>)}
              </motion.div>
            )}
          </AnimatePresence>


          <motion.button
            className="btn" onClick={launch} disabled={launching} whileTap={{ scale: 0.98 }}
            style={{
              padding: '14px 20px', fontSize: 14, fontWeight: 600, letterSpacing: '0.02em',
              fontFamily: "'Space Grotesk',sans-serif",
              background: isRedMode ? '#dc2626' : undefined,
              boxShadow: isRedMode ? '0 4px 16px rgba(225,29,72,0.2)' : undefined,
              transition: 'background 0.6s ease, box-shadow 0.6s ease',
            }}>
            {launching ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                <span style={{ width: 14, height: 14, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.25)', borderTopColor: '#fff', display: 'inline-block' }} className="spin-slow" />
                {isRedMode ? 'Starting Debate…' : 'Initialising Pipeline…'}
              </span>
            ) : isRedMode ? 'Launch Red Mode →' : 'Launch Analysis →'}
          </motion.button>
        </motion.div>
      </div>

      {/* Footer */}
      <div style={{ padding: '16px 32px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="mono" style={{ fontSize: 10 }}>DS-AGENT-TEAM v2.0</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {isRedMode
            ? <><span className="mono" style={{ fontSize: 10, color: '#dc2626' }}>20 personas</span><span className="mono" style={{ fontSize: 10, color: '#dc2626' }}>3 rounds</span></>
            : <><span className="mono" style={{ fontSize: 10 }}>10 agents</span><span className="mono" style={{ fontSize: 10 }}>3 phases</span></>
          }
          <span className="mono" style={{ fontSize: 10 }}>localhost:8000</span>
        </div>
      </div>
    </div>
    </>
  )
}
