'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API = 'http://localhost:8000'

interface Entry { role: string; agent: string; content: string; metadata: Record<string, unknown> }

const AGENT_META: Record<string, { label: string; icon: string; color: string; role: string }> = {
  explorer:         { label: 'Explorer',        icon: '◉', color: '#7c6fcd', role: 'Data Scout'       },
  skeptic:          { label: 'Skeptic',          icon: '⚠', color: '#d46b8a', role: 'Quality Guard'    },
  statistician:     { label: 'Statistician',     icon: '∑', color: '#4a9fd4', role: 'Numbers Expert'   },
  feature_engineer: { label: 'Feature Engineer', icon: '⟁', color: '#3db87a', role: 'Signal Extractor' },
  ethicist:         { label: 'Ethicist',         icon: '⚖', color: '#d4874a', role: 'Bias Detector'    },
  pragmatist:       { label: 'Pragmatist',       icon: '◈', color: '#c4a832', role: 'Reality Check'    },
  devil_advocate:   { label: 'Devil Advocate',   icon: '⛧', color: '#e63030', role: 'Critical Thinker' },
  optimizer:        { label: 'Optimizer',        icon: '⚡', color: '#8a7cd4', role: 'Efficiency Expert'},
  architect:        { label: 'Architect',        icon: '⬡', color: '#a86cd4', role: 'System Designer'  },
  storyteller:      { label: 'Storyteller',      icon: '✦', color: '#d4a8c4', role: 'Insight Narrator' },
  compactor:        { label: 'Compactor',        icon: '◎', color: '#888',    role: 'Context Manager'  },
  system:           { label: 'System',           icon: '◌', color: '#666',    role: 'Context'          },
  data_profiler:    { label: 'Data Profiler',    icon: '⊙', color: '#22d3ee', role: 'Auto Profiler'    },
}

function agentKey(raw: string): string {
  return raw?.toLowerCase().replace(/[\s']+/g, '_').replace(/[^a-z_]/g, '') ?? 'unknown'
}

interface NodeData { key: string; label: string; icon: string; color: string; role: string; content: string }

export default function ResultsPage() {
  const { id }  = useParams<{ id: string }>()
  const router  = useRouter()

  const [result,     setResult]     = useState<{ run_id: string; entries: Entry[]; error?: string } | null>(null)
  const [loading,    setLoading]    = useState(true)
  const [selected,   setSelected]   = useState<NodeData | null>(null)
  const [showReport, setShowReport] = useState(false)

  useEffect(() => {
    let attempts = 0
    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/result/${id}`)
        const d = await r.json()
        if (d.run_id || d.error) { setResult(d); setLoading(false); return }
      } catch {}
      if (++attempts < 20) setTimeout(poll, 2000)
      else setLoading(false)
    }
    poll()
  }, [id])

  const nodes = useMemo<NodeData[]>(() => {
    if (!result?.entries) return []
    const seen = new Map<string, string>()
    result.entries.forEach(e => {
      const k = agentKey(e.agent)
      if (!seen.has(k) && e.content && e.role !== 'task') seen.set(k, e.content)
    })
    return Array.from(seen.entries()).map(([k, content]) => {
      const m = AGENT_META[k]
      return {
        key:     k,
        label:   m?.label ?? k.replace(/_/g, ' '),
        icon:    m?.icon  ?? '◌',
        color:   m?.color ?? '#666',
        role:    m?.role  ?? '',
        content,
      }
    })
  }, [result])

  const report = useMemo(() => {
    if (!result?.entries) return ''
    return result.entries
      .filter(e => e.content && !['task', 'dataset_context'].includes(e.role))
      .map(e => {
        const m = AGENT_META[agentKey(e.agent)]
        const label = m?.label ?? e.agent
        return `## ${label}\n\n${e.content}`
      })
      .join('\n\n---\n\n')
  }, [result])

  const downloadReport = useCallback(() => {
    const blob = new Blob([report], { type: 'text/markdown' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `analysis_${id}.md`; a.click()
    URL.revokeObjectURL(url)
  }, [report, id])

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 40, height: 40, borderRadius: '50%', border: '2px solid rgba(230,48,48,0.2)', borderTopColor: '#e63030', margin: '0 auto 20px', animation: 'spin-slow 0.9s linear infinite' }} />
        <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: 'rgba(255,255,255,0.25)', letterSpacing: '0.12em' }}>LOADING RESULTS</div>
      </div>
    </div>
  )

  // ── Error ────────────────────────────────────────────────────────────────
  if (result?.error) return (
    <div style={{ minHeight: '100vh', background: '#0a0a0a', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
      <div style={{ maxWidth: 480, width: '100%', background: '#111', border: '1px solid rgba(230,48,48,0.25)', borderRadius: 18, padding: '28px' }}>
        <div style={{ fontSize: 13, color: '#f87171', fontWeight: 600, marginBottom: 12 }}>❌ Pipeline Error</div>
        <pre style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.3)', whiteSpace: 'pre-wrap', maxHeight: 240, overflow: 'auto', fontFamily: "'JetBrains Mono',monospace" }}>{result.error}</pre>
        <button className="btn-ghost" onClick={() => router.push('/')} style={{ marginTop: 16, width: '100%' }}>← Home</button>
      </div>
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', background: 'transparent', display: 'flex', flexDirection: 'column' }}>


      {/* Nav */}
      <nav style={{
        position: 'sticky', top: 0, zIndex: 100,
        padding: '16px 32px',
        background: 'rgba(10,10,10,0.92)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 26, height: 26, borderRadius: 7,
            background: 'linear-gradient(135deg, #e63030, #8b0000)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, color: '#fff',
          }}>◆</div>
          <span style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 600, fontSize: 14 }}>DS Agent Team</span>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono',monospace" }}>/ {id}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-ghost" onClick={() => setShowReport(true)} style={{ fontSize: 12 }}>Full Report</button>
          <button className="btn-outline" onClick={downloadReport} style={{ fontSize: 12 }}>↓ Export .md</button>
          <button className="btn-ghost" onClick={() => router.push('/')} style={{ fontSize: 12 }}>← Home</button>
        </div>
      </nav>

      {/* Main content */}
      <div style={{ flex: 1, padding: '40px 32px', maxWidth: 1200, margin: '0 auto', width: '100%', position: 'relative', zIndex: 10 }}>

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} style={{ marginBottom: 36 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <span style={{ color: '#34d399', fontSize: 18 }}>✓</span>
            <h1 style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 26, letterSpacing: '-0.02em' }}>
              Analysis Complete
            </h1>
          </div>
          <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 14 }}>
            {nodes.length} agents completed their analysis. Click any card to read their full output.
          </p>
        </motion.div>

        {/* Agent cards grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
          {nodes.map((node, i) => (
            <motion.div
              key={node.key}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              onClick={() => setSelected(node)}
              style={{
                padding: '18px 20px',
                borderRadius: 16,
                background: '#111111',
                border: `1px solid rgba(255,255,255,0.06)`,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
                overflow: 'hidden',
              }}
              whileHover={{
                borderColor: `${node.color}44`,
                backgroundColor: `${node.color}06`,
                y: -2,
              }}
            >
              {/* Top color bar */}
              <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${node.color}, transparent)` }} />

              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 11,
                  background: `${node.color}14`,
                  border: `1px solid ${node.color}30`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, color: node.color,
                }}>
                  {node.icon}
                </div>
                <div>
                  <div style={{ fontFamily: "'Inter',sans-serif", fontWeight: 600, fontSize: 14, color: 'rgba(255,255,255,0.85)' }}>{node.label}</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)', marginTop: 1 }}>{node.role}</div>
                </div>
              </div>

              <p style={{
                fontSize: 12, color: 'rgba(255,255,255,0.3)', lineHeight: 1.6,
                overflow: 'hidden', display: '-webkit-box',
                WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                fontFamily: "'Inter',sans-serif",
              }}>
                {node.content.replace(/#+\s/g, '').slice(0, 160)}…
              </p>

              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                <span style={{ fontSize: 11, color: node.color, fontFamily: "'Inter',sans-serif", fontWeight: 500 }}>Read output →</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── Selected agent panel ── */}
      <AnimatePresence>
        {selected && !showReport && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelected(null)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 200, backdropFilter: 'blur(4px)' }}
            />
            {/* Drawer */}
            <motion.div
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              style={{
                position: 'fixed', right: 0, top: 0, bottom: 0, zIndex: 201,
                width: 'min(560px, 100vw)',
                background: '#0f0f0f',
                borderLeft: `1px solid ${selected.color}30`,
                display: 'flex', flexDirection: 'column',
                boxShadow: `-20px 0 60px rgba(0,0,0,0.5)`,
              }}
            >
              {/* Top accent */}
              <div style={{ height: 2, background: `linear-gradient(90deg, ${selected.color}, ${selected.color}33)` }} />

              {/* Header */}
              <div style={{ padding: '24px 28px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 4 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 14,
                    background: `${selected.color}14`,
                    border: `1px solid ${selected.color}33`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 22, color: selected.color,
                  }}>
                    {selected.icon}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 18, color: selected.color }}>{selected.label}</div>
                    <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>{selected.role}</div>
                  </div>
                  <button
                    onClick={() => setSelected(null)}
                    style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >✕</button>
                </div>
              </div>

              {/* Content */}
              <div style={{ flex: 1, overflow: 'auto', padding: '20px 28px' }}>
                <div className="report">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.content}</ReactMarkdown>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Full report modal ── */}
      <AnimatePresence>
        {showReport && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setShowReport(false)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 200, backdropFilter: 'blur(6px)' }}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.97, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              style={{
                position: 'fixed', inset: '5vh 5vw', zIndex: 201,
                background: '#0f0f0f',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 20,
                display: 'flex', flexDirection: 'column',
                boxShadow: '0 40px 120px rgba(0,0,0,0.7)',
              }}
            >
              <div style={{ padding: '22px 28px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 18 }}>Full Analysis Report</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', marginTop: 2, fontFamily: "'JetBrains Mono',monospace" }}>Run {id}</div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn-outline" onClick={downloadReport} style={{ fontSize: 12 }}>↓ Export</button>
                  <button onClick={() => setShowReport(false)} style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
                </div>
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: '24px 36px', maxWidth: 860, margin: '0 auto', width: '100%' }}>
                <div className="report">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
