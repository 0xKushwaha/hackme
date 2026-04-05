'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import dynamic from 'next/dynamic'
import PipelineGraph, { PIPELINE_NODES, NodeData } from '@/components/PipelineGraph'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MOCK_STEPS, MOCK_RESULT_ENTRIES } from '@/lib/mockPipeline'

const API = 'http://localhost:8000'
// Minimalist Monochrome Accent — Phase 1
const ACCENT = '#ffffff'

function agentKey(raw: string): string {
  return raw?.toLowerCase().replace(/[\s']+/g, '_').replace(/[^a-z_]/g, '') ?? 'unknown'
}

function buildNodes(
  entries: { agent: string; role: string; content: string }[],
  agentResults?: Record<string, string>,
): NodeData[] {
  const contentMap = new Map<string, string>()
  if (agentResults) {
    for (const [key, val] of Object.entries(agentResults)) {
      if (val) contentMap.set(agentKey(key), val)
    }
  }
  entries.forEach(e => {
    const k = agentKey(e.agent)
    if (!contentMap.has(k) && e.content && e.role !== 'task') contentMap.set(k, e.content)
  })
  return PIPELINE_NODES.map(n => ({ ...n, content: contentMap.get(n.key) ?? '' }))
}

type View = 'graph' | 'summary'

export default function RunPage() {
  const { id }  = useParams<{ id: string }>()
  const router  = useRouter()

  const [activeAgent,  setActiveAgent]  = useState('')
  const [doneAgents,   setDoneAgents]   = useState<string[]>([])
  const [done,         setDone]         = useState(false)
  const [error,        setError]        = useState('')
  const [nodes,        setNodes]        = useState<NodeData[]>([])
  const [view,         setView]         = useState<View>('graph')
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [leaving,      setLeaving]      = useState(false)

  const goHome = useCallback(() => setLeaving(true), [])

  const doneRef   = useRef(false)
  const cursorRef = useRef(0)
  const timerRef  = useRef<NodeJS.Timeout | null>(null)

  const downloadReport = useCallback(() => {
    const lines: string[] = []
    for (const n of nodes) {
      if (!n.content) continue
      lines.push(`# ${n.label}\n\n${n.content}\n\n---\n`)
    }
    if (!lines.length) return
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `analysis_${id}.md`; a.click()
    URL.revokeObjectURL(url)
  }, [nodes, id])

  const isTest = id.startsWith('test-')

  useEffect(() => {
    if (isTest) return
    try {
      const cached = sessionStorage.getItem(`run_result_${id}`)
      if (cached) {
        const data = JSON.parse(cached)
        if (data.agent_results || data.entries) {
          setNodes(buildNodes(data.entries ?? [], data.agent_results))
          setDoneAgents(Object.keys(data.agent_results ?? {}))
          doneRef.current = true
          setDone(true)
        }
      }
    } catch {}
  }, [id, isTest])

  useEffect(() => {
    if (!isTest) return
    let cancelled = false
    const delay = (ms: number) => new Promise<void>(r => setTimeout(r, ms))
    const run = async () => {
      await delay(600)
      const doneSoFar: string[] = []
      for (const step of MOCK_STEPS) {
        if (cancelled) return
        setActiveAgent(step.agent)
        await delay(step.durationMs)
        if (cancelled) return
        doneSoFar.push(step.agent)
        setDoneAgents([...doneSoFar])
        setActiveAgent('')
      }
      if (cancelled) return
      doneRef.current = true
      setDone(true)
      setNodes(buildNodes(MOCK_RESULT_ENTRIES))
    }
    run()
    return () => { cancelled = true }
  }, [isTest, id])

  const poll = useCallback(async () => {
    if (doneRef.current) return
    try {
      const r = await fetch(`${API}/api/poll/${id}?cursor=${cursorRef.current}`)
      const d = await r.json()
      cursorRef.current = d.cursor ?? cursorRef.current
      if (d.agent) setActiveAgent(d.agent)
      if (d.doneAgents?.length) setDoneAgents(d.doneAgents as string[])
      if (d.everActive?.length)  setDoneAgents(d.everActive as string[])
      if (d.done) {
        doneRef.current = true; setDone(true)
        if (d.error) {
          setError(d.error)
        } else {
          try {
            const res  = await fetch(`${API}/api/result/${id}`)
            const data = await res.json()
            if (data.entries || data.agent_results) {
              setNodes(buildNodes(data.entries ?? [], data.agent_results))
              try { sessionStorage.setItem(`run_result_${id}`, JSON.stringify(data)) } catch {}
            }
          } catch {}
        }
      }
    } catch {}
    if (!doneRef.current) timerRef.current = setTimeout(poll, 1500)
  }, [id])

  useEffect(() => {
    if (isTest) return
    poll()
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [poll, isTest])

  const selNode  = selectedNode ? nodes.find(n => n.key === selectedNode) : null
  const panelOpen = !!(selNode?.content)

  return (
    <div style={{
      height: '100vh', overflow: 'hidden',
      background: 'transparent',
      color: '#f0f0f0', fontFamily: 'Inter, sans-serif',
      display: 'flex', flexDirection: 'column',
    }}>

      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{
        padding: '12px 24px', flexShrink: 0,
        borderBottom: `1px solid ${ACCENT}18`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(1,8,20,0.85)', backdropFilter: 'blur(20px)',
        zIndex: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: ACCENT, fontWeight: 700, letterSpacing: '0.12em' }}>
            ◈ ANALYSIS
          </span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>{id}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {done && !error && (
            <>
              {(['graph', 'summary'] as View[]).map(v => (
                <button key={v} onClick={() => setView(v)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0',
                  fontSize: 11, fontFamily: "'JetBrains Mono',monospace",
                  color: view === v ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.35)',
                  borderBottom: view === v ? '1px solid rgba(255,255,255,0.5)' : '1px solid transparent',
                  transition: 'all 0.15s', letterSpacing: '0.06em', textTransform: 'uppercase',
                }}>{v}</button>
              ))}
              <button onClick={downloadReport} style={{
                padding: '4px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 10,
                fontFamily: 'JetBrains Mono',
                background: `${ACCENT}10`, border: `1px solid ${ACCENT}30`,
                color: ACCENT, transition: 'all 0.15s',
              }}>↓ Report</button>
            </>
          )}
          {done
            ? <span style={{ fontSize: 10, color: '#4ade80', fontFamily: 'JetBrains Mono' }}>✓ complete</span>
            : !error && <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT, display: 'inline-block', animation: 'pulse-dot 1.4s ease-in-out infinite' }} />
          }
          <button onClick={goHome}
            style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: 17, padding: 0, lineHeight: 1 }}>
            ←
          </button>
        </div>
      </div>

      {/* ── Main area ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>

        {/* Graph */}
        {view === 'graph' && (
          <div style={{ position: 'absolute', inset: 0, zIndex: 1 }}>
            <PipelineGraph
              activeAgent={activeAgent} doneAgents={doneAgents} done={done} nodes={nodes}
              selectedKey={selectedNode} onSelect={setSelectedNode}
            />
          </div>
        )}

        {/* Summary view */}
        {view === 'summary' && done && (
          <div style={{ position: 'absolute', inset: 0, overflowY: 'auto', zIndex: 1 }}>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '28px 32px 8px' }}>
              <h1 style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 22, letterSpacing: '-0.02em' }}>
                Analysis Complete
              </h1>
              <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12.5, marginTop: 4 }}>
                {nodes.filter(n => n.content).length} agents — run <span style={{ fontFamily: "'JetBrains Mono',monospace", color: 'rgba(255,255,255,0.4)' }}>{id}</span>
              </p>
            </motion.div>
            <SummaryView nodes={nodes} />
          </div>
        )}

        {/* ── Floating right content panel ──────────────────────── */}
        <AnimatePresence>
          {panelOpen && selNode && (
            <motion.div
              key="content-panel"
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 40 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              style={{
                position: 'absolute', top: 16, right: 16, bottom: 16,
                width: 460, zIndex: 15,
                background: 'rgba(1,8,20,0.93)', backdropFilter: 'blur(24px)',
                border: `1px solid ${selNode.color}30`,
                borderRadius: 16, overflow: 'hidden',
                display: 'flex', flexDirection: 'column',
                boxShadow: `0 24px 64px rgba(0,0,0,0.7), 0 0 40px ${selNode.color}12`,
              }}
            >
              <div style={{ height: 2, background: `linear-gradient(90deg, ${selNode.color}, transparent)`, flexShrink: 0 }} />
              <div style={{
                padding: '14px 18px', flexShrink: 0,
                borderBottom: `1px solid ${selNode.color}18`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 9, background: `${selNode.color}18`, border: `1px solid ${selNode.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, color: selNode.color, flexShrink: 0 }}>
                    {selNode.icon}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: selNode.color, fontFamily: "'Space Grotesk',sans-serif" }}>{selNode.label}</div>
                    <div style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.28)', marginTop: 1 }}>{selNode.role}</div>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  style={{ width: 26, height: 26, borderRadius: 7, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >✕</button>
              </div>
              <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', scrollbarWidth: 'thin' }}>
                <div className="report">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selNode.content}</ReactMarkdown>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Log ticker ────────────────────────────────────────── */}
        {!done && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
            padding: '7px 18px',
            background: 'rgba(1,6,14,0.75)', backdropFilter: 'blur(8px)',
            borderTop: `1px solid ${ACCENT}10`,
          }}>
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: 'rgba(255,255,255,0.2)' }}>
              {activeAgent ? `running ${activeAgent}…` : 'Initialising…'}
            </span>
          </div>
        )}
      </div>

      {/* ── Error overlay ──────────────────────────────────────────── */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
          }}
        >
          <div style={{ maxWidth: 480, width: '100%', margin: '0 24px', background: 'rgba(1,8,20,0.96)', border: `1px solid ${ACCENT}25`, borderRadius: 18, padding: 28 }}>
            <div style={{ fontSize: 13, color: '#f87171', fontWeight: 600, marginBottom: 12 }}>Pipeline Failed</div>
            <pre style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflow: 'auto', fontFamily: "'JetBrains Mono',monospace" }}>{error}</pre>
            <button onClick={goHome} style={{
              marginTop: 16, width: '100%', padding: '9px', borderRadius: 8, cursor: 'pointer',
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              color: 'rgba(255,255,255,0.4)', fontSize: 12, fontFamily: "'JetBrains Mono',monospace",
            }}>← Return Home</button>
          </div>
        </motion.div>
      )}

      {/* ── Page-enter overlay (fades out on mount) ──────────────── */}
      <motion.div
        initial={{ opacity: 1 }}
        animate={{ opacity: 0 }}
        transition={{ duration: 0.35, ease: 'easeInOut' }}
        style={{ position: 'fixed', inset: 0, zIndex: 998, background: '#000', pointerEvents: 'none' }}
      />

      {/* ── Page-leave overlay ────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: leaving ? 1 : 0 }}
        transition={{ duration: 0.35, ease: 'easeInOut' }}
        onAnimationComplete={() => { if (leaving) router.push('/') }}
        style={{ position: 'fixed', inset: 0, zIndex: 999, background: '#000', pointerEvents: leaving ? 'all' : 'none' }}
      />

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.75); }
        }
        .report h1 { font-size: 17px; font-weight: 700; color: #fff; margin: 20px 0 10px; }
        .report h2 { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.88); margin: 16px 0 8px; border-bottom: 1px solid ${ACCENT}28; padding-bottom: 6px; }
        .report h3 { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.75); margin: 13px 0 5px; }
        .report p  { color: rgba(255,255,255,0.7); margin-bottom: 10px; font-size: 13px; line-height: 1.72; }
        .report ul { padding-left: 20px; margin-bottom: 10px; }
        .report li { color: rgba(255,255,255,0.7); font-size: 13px; line-height: 1.7; margin-bottom: 4px; }
        .report strong { color: rgba(255,255,255,0.92); font-weight: 600; }
        .report em { color: rgba(255,255,255,0.5); font-style: italic; }
        .report code { background: ${ACCENT}14; color: #bae6fd; border: 1px solid ${ACCENT}22; border-radius: 4px; padding: 1px 5px; font-size: 11.5px; }
        .report hr { border: none; border-top: 1px solid ${ACCENT}18; margin: 14px 0; }
        .report blockquote { border-left: 2px solid ${ACCENT}40; padding-left: 12px; color: rgba(255,255,255,0.4); font-style: italic; margin: 10px 0; }
      `}</style>
    </div>
  )
}

// ── Summary view ───────────────────────────────────────────────────────

function SummaryCard({ node, expanded, onToggle, cardRef }: {
  node: NodeData; expanded: boolean; onToggle: () => void
  cardRef?: (el: HTMLDivElement | null) => void
}) {
  return (
    <div
      ref={cardRef}
      onClick={onToggle}
      style={{
        borderRadius: 16, cursor: 'pointer',
        background: expanded ? 'rgba(1,8,20,0.92)' : 'rgba(1,6,16,0.6)',
        backdropFilter: 'blur(18px)',
        border: `1px solid ${expanded ? node.color + '50' : node.color + '20'}`,
        position: 'relative', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        boxShadow: expanded ? `0 0 0 1px ${node.color}20, 0 16px 48px rgba(0,0,0,0.5)` : 'none',
        transition: 'border-color 0.35s ease, background 0.35s ease, box-shadow 0.35s ease',
        gridColumn: expanded ? '1 / -1' : 'auto',
      }}
    >
      <div style={{ height: 2, background: `linear-gradient(90deg, ${node.color}, transparent)`, flexShrink: 0 }} />
      <div style={{ padding: '14px 18px 12px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${node.color}15`, flexShrink: 0 }}>
        <div style={{ width: 32, height: 32, borderRadius: 9, background: `${node.color}14`, border: `1px solid ${node.color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: node.color, flexShrink: 0 }}>{node.icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: node.color }}>{node.label}</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>{node.role}</div>
        </div>
        <div style={{ fontSize: 10, color: `${node.color}99`, fontFamily: "'JetBrains Mono',monospace", letterSpacing: '0.04em', flexShrink: 0 }}>
          {expanded ? '▲ collapse' : '▼ expand'}
        </div>
      </div>
      <div style={{ position: 'relative', overflow: 'hidden', maxHeight: expanded ? '9999px' : '280px', transition: expanded ? 'max-height 0.55s ease' : 'max-height 0.35s ease' }}>
        <div className="report" style={{ padding: '14px 20px 18px', fontSize: '0.82rem' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{node.content}</ReactMarkdown>
        </div>
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 64, background: 'linear-gradient(to bottom, transparent, rgba(1,6,16,0.97))', pointerEvents: 'none', opacity: expanded ? 0 : 1, transition: 'opacity 0.3s ease' }} />
      </div>
    </div>
  )
}

const SUMMARY_ORDER = ['final_report', 'statistician', 'skeptic', 'ethicist', 'optimizer', 'architect', 'devil_advocate', 'feature_engineer', 'explorer', 'pragmatist']

function SummaryView({ nodes }: { nodes: NodeData[] }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const nodeMap  = Object.fromEntries(nodes.map(n => [n.key, n]))
  const hero     = nodeMap['final_report'] ?? nodes.find(n => n.content)
  const rest     = SUMMARY_ORDER.filter(k => k !== 'final_report' && nodeMap[k]?.content)

  const toggle = (key: string) => {
    const opening = expanded !== key
    setExpanded(opening ? key : null)
    if (opening) setTimeout(() => cardRefs.current[key]?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60)
  }

  const heroExpanded = expanded === (hero?.key ?? '')

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ padding: '12px 32px 60px' }}>
      {hero?.content && (
        <div
          ref={el => { cardRefs.current[hero.key] = el }}
          onClick={() => toggle(hero.key)}
          style={{
            marginBottom: 20, borderRadius: 18, cursor: 'pointer',
            background: heroExpanded ? 'rgba(1,8,20,0.92)' : `${hero.color}07`,
            border: `1px solid ${heroExpanded ? hero.color + '45' : hero.color + '22'}`,
            position: 'relative', overflow: 'hidden',
            boxShadow: heroExpanded ? `0 0 0 1px ${hero.color}20, 0 16px 48px rgba(0,0,0,0.5)` : 'none',
            transition: 'border-color 0.35s ease, background 0.35s ease, box-shadow 0.35s ease',
          }}
        >
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, ${hero.color}, ${hero.color}22)` }} />
          <div style={{ padding: '20px 28px 14px', display: 'flex', alignItems: 'center', gap: 14, borderBottom: `1px solid ${hero.color}18` }}>
            <div style={{ width: 48, height: 48, borderRadius: 14, background: `${hero.color}18`, border: `1px solid ${hero.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: hero.color, flexShrink: 0 }}>{hero.icon}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 17, color: hero.color }}>{hero.label}</div>
              <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>Full Report</div>
            </div>
            <div style={{ fontSize: 11, color: `${hero.color}99`, fontFamily: "'JetBrains Mono',monospace" }}>
              {heroExpanded ? '▲ collapse' : '▼ expand'}
            </div>
          </div>
          <div style={{ position: 'relative', overflow: 'hidden', maxHeight: heroExpanded ? '9999px' : '340px', transition: heroExpanded ? 'max-height 0.55s ease' : 'max-height 0.35s ease' }}>
            <div className="report" style={{ padding: '20px 28px 24px' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{hero.content}</ReactMarkdown>
            </div>
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 80, background: 'linear-gradient(to bottom, transparent, rgba(1,6,16,0.97))', pointerEvents: 'none', opacity: heroExpanded ? 0 : 1, transition: 'opacity 0.3s ease' }} />
          </div>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
        {rest.map(k => (
          <div key={k} style={{ gridColumn: expanded === k ? '1 / -1' : 'auto' }}>
            <SummaryCard node={nodeMap[k]!} expanded={expanded === k} onToggle={() => toggle(k)} cardRef={el => { cardRefs.current[k] = el }} />
          </div>
        ))}
      </div>
    </motion.div>
  )
}
