'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MOCK_RESULT_ENTRIES } from '@/lib/mockPipeline'
import ResultsGraph from '@/components/ResultsGraph'

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
  final_report:     { label: 'Final Report',     icon: '★', color: '#f0c040', role: 'Pipeline Output'   },
  compactor:        { label: 'Compactor',        icon: '◎', color: '#888',    role: 'Context Manager'  },
  system:           { label: 'System',           icon: '◌', color: '#666',    role: 'Context'          },
  data_profiler:    { label: 'Data Profiler',    icon: '⊙', color: '#22d3ee', role: 'Auto Profiler'    },
}

function agentKey(raw: string): string {
  return raw?.toLowerCase().replace(/[\s']+/g, '_').replace(/[^a-z_]/g, '') ?? 'unknown'
}

interface NodeData { key: string; label: string; icon: string; color: string; role: string; content: string }

type ResultView = 'cards' | 'report' | 'graph' | 'summary'

export default function ResultsPage() {
  const { id }  = useParams<{ id: string }>()
  const router  = useRouter()

  const [result,     setResult]     = useState<{ run_id: string; entries: Entry[]; error?: string } | null>(null)
  const [loading,    setLoading]    = useState(true)
  const [selected,   setSelected]   = useState<NodeData | null>(null)
  const [resultView, setResultView] = useState<ResultView>('graph')

  useEffect(() => {
    // Test mode — use mock data instantly, no API call
    if (id.startsWith('test-')) {
      setResult({ run_id: id, entries: MOCK_RESULT_ENTRIES })
      setLoading(false)
      return
    }

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

  // Loading
  if (loading) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 40, height: 40, borderRadius: '50%', border: '2px solid rgba(230,48,48,0.2)', borderTopColor: '#e63030', margin: '0 auto 20px', animation: 'spin-slow 0.9s linear infinite' }} />
        <div style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 12, color: 'rgba(255,255,255,0.25)', letterSpacing: '0.12em' }}>LOADING RESULTS</div>
      </div>
    </div>
  )

  // Error
  if (result?.error) return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
      <div style={{ maxWidth: 480, width: '100%', background: 'rgba(8,2,2,0.55)', backdropFilter: 'blur(20px)', border: '1px solid rgba(230,48,48,0.25)', borderRadius: 18, padding: '28px' }}>
        <div style={{ fontSize: 13, color: '#f87171', fontWeight: 600, marginBottom: 12 }}>Pipeline Error</div>
        <pre style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.3)', whiteSpace: 'pre-wrap', maxHeight: 240, overflow: 'auto', fontFamily: "'JetBrains Mono',monospace" }}>{result.error}</pre>
        <button className="btn-ghost" onClick={() => router.push('/')} style={{ marginTop: 16, width: '100%' }}>← Home</button>
      </div>
    </div>
  )

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* Nav */}
      <nav style={{
        position: 'fixed', top: 16, left: '50%', transform: 'translateX(-50%)',
        zIndex: 100, width: 'calc(100% - 48px)', maxWidth: 1200,
        padding: '12px 24px',
        background: 'rgba(6,2,2,0.65)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 13,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.2)', fontFamily: "'JetBrains Mono',monospace" }}>/ results</span>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* View toggle */}
          <div className="view-toggle">
            <button className={resultView === 'graph'   ? 'active' : ''} onClick={() => setResultView('graph')}>Graph</button>
            <button className={resultView === 'summary' ? 'active' : ''} onClick={() => setResultView('summary')}>Summary</button>
            <button className={resultView === 'cards'   ? 'active' : ''} onClick={() => setResultView('cards')}>Agents</button>
            <button className={resultView === 'report'  ? 'active' : ''} onClick={() => setResultView('report')}>Report</button>
          </div>
          <button className="btn-outline" onClick={downloadReport} style={{ fontSize: 11.5, padding: '6px 14px' }}>↓ Export .md</button>
          <button className="btn-ghost" onClick={() => router.push('/')} style={{ fontSize: 11.5, padding: '6px 12px' }}>← Home</button>
        </div>
      </nav>

      {/* Graph view — full screen */}
      {resultView === 'graph' && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: 'radial-gradient(ellipse at 40% 50%, #0c0818 0%, #06020e 55%, #030008 100%)' }} />
          <div style={{ position: 'fixed', inset: 0, top: 60, zIndex: 1 }}>
            <ResultsGraph nodes={nodes} />
          </div>
        </>
      )}

      {/* Main content */}
      <div style={{ flex: 1, paddingTop: 80, maxWidth: 1200, margin: '0 auto', width: '100%', position: 'relative', zIndex: 10, display: resultView === 'graph' ? 'none' : 'flex', flexDirection: 'column' }}>

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '28px 32px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: 'rgba(52,211,153,0.1)', border: '1px solid rgba(52,211,153,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ color: '#34d399', fontSize: 18 }}>✓</span>
            </div>
            <div>
              <h1 style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 24, letterSpacing: '-0.02em' }}>
                Analysis Complete
              </h1>
              <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12.5, marginTop: 2 }}>
                {nodes.length} agents completed — Run <span style={{ fontFamily: "'JetBrains Mono',monospace", color: 'rgba(255,255,255,0.4)' }}>{id}</span>
              </p>
            </div>
          </div>

          {/* Completed agents strip */}
          <div style={{ display: 'flex', gap: 6, marginTop: 16, marginBottom: 24, flexWrap: 'wrap' }}>
            {nodes.map((node, i) => (
              <motion.div key={node.key}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => { setSelected(node); setResultView('cards') }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 10px', borderRadius: 8,
                  background: `${node.color}0a`,
                  border: `1px solid ${node.color}20`,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                <span style={{ fontSize: 12, color: node.color }}>{node.icon}</span>
                <span style={{ fontSize: 10.5, color: `${node.color}cc`, fontFamily: "'JetBrains Mono',monospace" }}>{node.label}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Cards view */}
        {resultView === 'cards' && (
          <div style={{ padding: '0 32px 40px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
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
                    background: 'rgba(8,2,2,0.55)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255,255,255,0.06)',
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
        )}

        {/* Report view — inline full report */}
        {resultView === 'report' && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ padding: '0 32px 60px' }}
          >
            <div style={{
              background: 'rgba(8,2,2,0.55)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255,255,255,0.07)',
              borderRadius: 18,
              overflow: 'hidden',
            }}>
              {/* Report header */}
              <div style={{ padding: '20px 28px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 16 }}>Full Analysis Report</div>
                  <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.2)', marginTop: 2, fontFamily: "'JetBrains Mono',monospace" }}>
                    {nodes.length} sections — Run {id}
                  </div>
                </div>
                <button className="btn-outline" onClick={downloadReport} style={{ fontSize: 11.5 }}>↓ Download</button>
              </div>

              {/* Report sections — expandable like MiroFish */}
              <div style={{ padding: '24px 32px', maxWidth: 820, margin: '0 auto' }}>
                {nodes.map((node, i) => (
                  <ReportSection key={node.key} node={node} index={i} />
                ))}
              </div>
            </div>
          </motion.div>
        )}
        {/* Summary view */}
        {resultView === 'summary' && (
          <SummaryView nodes={nodes} />
        )}

      </div>

      {/* Selected agent drawer */}
      <AnimatePresence>
        {selected && resultView === 'cards' && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelected(null)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 200, backdropFilter: 'blur(4px)' }}
            />
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
              <div style={{ height: 2, background: `linear-gradient(90deg, ${selected.color}, ${selected.color}33)` }} />
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
              <div style={{ flex: 1, overflow: 'auto', padding: '20px 28px' }}>
                <div className="report">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.content}</ReactMarkdown>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Summary view ─────────────────────────────────────────────────────────────
function extractBullets(content: string, max = 4): string[] {
  const lines = content.split('\n')
  const bullets: string[] = []
  for (const line of lines) {
    const m = line.match(/^[-*•]\s+(.+)/) ?? line.match(/^\d+\.\s+(.+)/)
    if (m) { bullets.push(m[1].trim()); if (bullets.length >= max) break }
  }
  if (bullets.length === 0) {
    // Fallback: first non-heading sentence
    const plain = content.replace(/#+\s[^\n]*/g, '').trim()
    const sentence = plain.split(/\.\s+/)[0]
    if (sentence) bullets.push(sentence.trim())
  }
  return bullets
}

function SummaryCard({ node, bullets }: { node: NodeData; bullets: string[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        padding: '18px 20px',
        borderRadius: 16,
        background: 'rgba(8,2,2,0.55)',
        backdropFilter: 'blur(18px)',
        border: `1px solid ${node.color}18`,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${node.color}, transparent)` }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10,
          background: `${node.color}14`, border: `1px solid ${node.color}30`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 15, color: node.color, flexShrink: 0,
        }}>{node.icon}</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: node.color }}>{node.label}</div>
          <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.25)' }}>{node.role}</div>
        </div>
      </div>
      <ul style={{ margin: 0, paddingLeft: 16 }}>
        {bullets.map((b, i) => (
          <li key={i} style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', lineHeight: 1.65, marginBottom: 4, fontFamily: "'Inter',sans-serif" }}>
            {b}
          </li>
        ))}
      </ul>
    </motion.div>
  )
}

const SUMMARY_AGENTS = ['storyteller', 'statistician', 'skeptic', 'ethicist', 'optimizer', 'architect', 'devil_advocate', 'feature_engineer', 'explorer', 'pragmatist']

function SummaryView({ nodes }: { nodes: NodeData[] }) {
  const nodeMap = Object.fromEntries(nodes.map(n => [n.key, n]))

  // Hero: storyteller first
  const hero = nodeMap['storyteller'] ?? nodes[0]
  const heroLines = hero ? extractBullets(hero.content, 5) : []

  const rest = SUMMARY_AGENTS.filter(k => k !== 'storyteller' && nodeMap[k])

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ padding: '0 32px 60px' }}>
      {/* Hero card */}
      {hero && (
        <div style={{
          marginBottom: 24,
          padding: '24px 28px',
          borderRadius: 18,
          background: `${hero.color}08`,
          border: `1px solid ${hero.color}25`,
          position: 'relative',
          overflow: 'hidden',
        }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, ${hero.color}, ${hero.color}33)` }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14,
              background: `${hero.color}18`, border: `1px solid ${hero.color}35`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22, color: hero.color,
            }}>{hero.icon}</div>
            <div>
              <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 17, color: hero.color }}>{hero.label}</div>
              <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>Key Takeaways</div>
            </div>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {heroLines.map((b, i) => (
              <li key={i} style={{ fontSize: 13.5, color: 'rgba(255,255,255,0.7)', lineHeight: 1.7, marginBottom: 6 }}>{b}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Grid of remaining agents */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
        {rest.map((k, i) => {
          const n = nodeMap[k]!
          return (
            <motion.div key={k} transition={{ delay: i * 0.04 }}>
              <SummaryCard node={n} bullets={extractBullets(n.content, 4)} />
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}

// Expandable report section (MiroFish-inspired)
function ReportSection({ node, index }: { node: NodeData; index: number }) {
  const [expanded, setExpanded] = useState(index === 0)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      style={{ marginBottom: 12 }}
    >
      <button
        onClick={() => setExpanded(v => !v)}
        style={{
          width: '100%', textAlign: 'left', cursor: 'pointer',
          padding: '14px 16px', borderRadius: expanded ? '12px 12px 0 0' : 12,
          background: expanded ? `${node.color}08` : 'rgba(255,255,255,0.02)',
          border: `1px solid ${expanded ? `${node.color}20` : 'rgba(255,255,255,0.05)'}`,
          borderBottom: expanded ? 'none' : `1px solid ${expanded ? `${node.color}20` : 'rgba(255,255,255,0.05)'}`,
          display: 'flex', alignItems: 'center', gap: 12,
          transition: 'all 0.2s',
        }}
      >
        <div style={{
          width: 32, height: 32, borderRadius: 9,
          background: `${node.color}12`,
          border: `1px solid ${node.color}25`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, color: node.color, flexShrink: 0,
        }}>
          {node.icon}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: expanded ? node.color : 'rgba(255,255,255,0.6)' }}>{node.label}</div>
          <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.2)', marginTop: 1 }}>{node.role}</div>
        </div>
        <motion.span
          animate={{ rotate: expanded ? 180 : 0 }}
          style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}
        >▼</motion.span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              padding: '16px 20px',
              borderRadius: '0 0 12px 12px',
              background: `${node.color}05`,
              border: `1px solid ${node.color}20`,
              borderTop: `1px solid ${node.color}10`,
            }}>
              <div className="report">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{node.content}</ReactMarkdown>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
