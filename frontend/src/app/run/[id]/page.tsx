'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import PipelineGraph, { PIPELINE_NODES, NodeData } from '@/components/PipelineGraph'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MOCK_STEPS, MOCK_RESULT_ENTRIES } from '@/lib/mockPipeline'

const API = 'http://localhost:8000'

function agentKey(raw: string): string {
  return raw?.toLowerCase().replace(/[\s']+/g, '_').replace(/[^a-z_]/g, '') ?? 'unknown'
}

function buildNodes(
  entries: { agent: string; role: string; content: string }[],
  agentResults?: Record<string, string>,
): NodeData[] {
  const contentMap = new Map<string, string>()
  // Primary source: agent_results (immune to compaction)
  if (agentResults) {
    for (const [key, val] of Object.entries(agentResults)) {
      if (val) contentMap.set(agentKey(key), val)
    }
  }
  // Fallback: entries (for backwards compat / mock mode)
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

  const doneRef  = useRef(false)
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

  // ── Restore from localStorage on mount ─────────────────────────────────────
  useEffect(() => {
    if (isTest) return
    try {
      const cached = localStorage.getItem(`run_result_${id}`)
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

  // ── Mock simulator ──────────────────────────────────────────────────────────
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

  // ── Real poll ───────────────────────────────────────────────────────────────
  const poll = useCallback(async () => {
    if (doneRef.current) return
    try {
      const r = await fetch(`${API}/api/poll/${id}?cursor=${cursorRef.current}`)
      const d = await r.json()
      cursorRef.current = d.cursor ?? cursorRef.current
      if (d.agent) setActiveAgent(d.agent)
      if (d.doneAgents?.length) setDoneAgents(d.doneAgents as string[])
      if (d.done) {
        doneRef.current = true; setDone(true)
        if (d.error) {
          setError(d.error)
        } else {
          // Fetch full results to populate node content
          try {
            const res  = await fetch(`${API}/api/result/${id}`)
            const data = await res.json()
            if (data.entries || data.agent_results) {
              setNodes(buildNodes(data.entries ?? [], data.agent_results))
              // Cache to localStorage so page refresh restores state
              try { localStorage.setItem(`run_result_${id}`, JSON.stringify(data)) } catch {}
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

  return (
    <div style={{ minHeight: '100vh', position: 'relative', zIndex: 1 }}>

      {/* Background */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: 'radial-gradient(ellipse at 40% 50%, #020c18 0%, #010a16 55%, #010810 100%)' }} />

      {/* Graph — always full screen */}
      {view === 'graph' && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1 }}>
          <PipelineGraph
            activeAgent={activeAgent} doneAgents={doneAgents} done={done} nodes={nodes}
            selectedKey={selectedNode} onSelect={setSelectedNode}
          />
        </div>
      )}

      {/* Output drawer — rendered at root level to escape graph's stacking context */}
      {(() => {
        const selNode = selectedNode ? nodes.find(n => n.key === selectedNode) : null
        if (!selNode?.content) return null
        return (
          <>
            <div onClick={() => setSelectedNode(null)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 500, backdropFilter: 'blur(4px)' }} />
            <div style={{
              position: 'fixed', right: 0, top: 0, bottom: 0, zIndex: 501,
              width: 'min(580px, 100vw)',
              background: '#030c1a',
              borderLeft: `1px solid ${selNode.color}35`,
              display: 'flex', flexDirection: 'column',
              boxShadow: `-24px 0 60px rgba(0,0,0,0.6)`,
            }}>
              <div style={{ height: 2, background: `linear-gradient(90deg, ${selNode.color}, ${selNode.color}22)` }} />
              <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 44, height: 44, borderRadius: 12, flexShrink: 0, background: `${selNode.color}15`, border: `1px solid ${selNode.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, color: selNode.color }}>
                  {selNode.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 16, color: selNode.color }}>{selNode.label}</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)', marginTop: 2 }}>{selNode.role}</div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedNode(null) }}
                  style={{ width: 28, height: 28, borderRadius: 7, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >✕</button>
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: '18px 24px' }}>
                <div className="report">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selNode.content}</ReactMarkdown>
                </div>
              </div>
            </div>
          </>
        )
      })()}

      {/* Summary — scrollable content area */}
      {view === 'summary' && done && (
        <div style={{ position: 'relative', zIndex: 10, paddingTop: 72, maxWidth: 1200, margin: '0 auto', width: '100%' }}>
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

      {/* Nav — appears once done */}
      {done && !error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          style={{ position: 'fixed', top: 16, left: 24, right: 24, zIndex: 100 }}
        >
          <div style={{
            maxWidth: 1200, margin: '0 auto',
            padding: '11px 24px',
            background: 'rgba(6,2,2,0.75)', backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.09)', borderRadius: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#f0c040', boxShadow: '0 0 8px #f0c04099', flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', fontFamily: "'JetBrains Mono',monospace" }}>complete</span>
            </div>
            <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
              {(['graph', 'summary'] as View[]).map(v => (
                <button key={v} onClick={() => setView(v)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0',
                  fontSize: 12, fontFamily: "'JetBrains Mono',monospace",
                  color: view === v ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.35)',
                  borderBottom: view === v ? '1px solid rgba(255,255,255,0.5)' : '1px solid transparent',
                  transition: 'all 0.15s', letterSpacing: '0.06em', textTransform: 'uppercase',
                }}>{v}</button>
              ))}
              <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.08)' }} />
              <button className="btn-outline" onClick={downloadReport} style={{ fontSize: 11.5, padding: '6px 14px' }}>↓ Report</button>
              <button className="btn-ghost" onClick={() => router.push('/')} style={{ fontSize: 11.5, padding: '6px 12px' }}>← Home</button>
            </div>
          </div>
        </motion.div>
      )}

      {/* Error overlay */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
          }}
        >
          <div style={{ maxWidth: 480, width: '100%', margin: '0 24px', background: 'rgba(8,2,2,0.9)', border: '1px solid rgba(230,48,48,0.25)', borderRadius: 18, padding: '28px' }}>
            <div style={{ fontSize: 13, color: '#f87171', fontWeight: 600, marginBottom: 12 }}>Pipeline Failed</div>
            <pre style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflow: 'auto', fontFamily: "'JetBrains Mono',monospace" }}>{error}</pre>
            <button className="btn-ghost" onClick={() => router.push('/')} style={{ marginTop: 16, width: '100%' }}>← Return Home</button>
          </div>
        </motion.div>
      )}
    </div>
  )
}

// ── Summary view ───────────────────────────────────────────────────────────────

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
        background: expanded ? 'rgba(12,4,4,0.88)' : 'rgba(8,2,2,0.55)',
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

      {/* Header */}
      <div style={{ padding: '14px 18px 12px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${node.color}15`, flexShrink: 0 }}>
        <div style={{ width: 32, height: 32, borderRadius: 9, background: `${node.color}14`, border: `1px solid ${node.color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: node.color, flexShrink: 0 }}>{node.icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: node.color }}>{node.label}</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>{node.role}</div>
        </div>
        <div style={{ fontSize: 10, color: `${node.color}99`, fontFamily: "'JetBrains Mono',monospace", letterSpacing: '0.04em', flexShrink: 0, transition: 'color 0.2s' }}>
          {expanded ? '▲ collapse' : '▼ expand'}
        </div>
      </div>

      {/* Content with smooth max-height transition */}
      <div style={{
        position: 'relative', overflow: 'hidden',
        maxHeight: expanded ? '9999px' : '280px',
        transition: expanded ? 'max-height 0.55s ease' : 'max-height 0.35s ease',
      }}>
        <div className="report" style={{ padding: '14px 20px 18px', fontSize: '0.82rem' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{node.content}</ReactMarkdown>
        </div>
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 64,
          background: 'linear-gradient(to bottom, transparent, rgba(8,2,2,0.97))',
          pointerEvents: 'none',
          opacity: expanded ? 0 : 1,
          transition: 'opacity 0.3s ease',
        }} />
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
    if (opening) {
      // After the grid reflows, scroll the card top into view
      setTimeout(() => {
        cardRefs.current[key]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 60)
    }
  }

  const heroExpanded = expanded === (hero?.key ?? '')

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ padding: '12px 32px 60px' }}>

      {/* Hero — Final Report */}
      {hero?.content && (
        <div
          ref={el => { cardRefs.current[hero.key] = el }}
          onClick={() => toggle(hero.key)}
          style={{
            marginBottom: 20, borderRadius: 18, cursor: 'pointer',
            background: heroExpanded ? 'rgba(12,4,4,0.88)' : `${hero.color}07`,
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
            <div style={{ fontSize: 11, color: `${hero.color}99`, fontFamily: "'JetBrains Mono',monospace", transition: 'color 0.2s' }}>
              {heroExpanded ? '▲ collapse' : '▼ expand'}
            </div>
          </div>
          <div style={{
            position: 'relative', overflow: 'hidden',
            maxHeight: heroExpanded ? '9999px' : '340px',
            transition: heroExpanded ? 'max-height 0.55s ease' : 'max-height 0.35s ease',
          }}>
            <div className="report" style={{ padding: '20px 28px 24px' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{hero.content}</ReactMarkdown>
            </div>
            <div style={{
              position: 'absolute', bottom: 0, left: 0, right: 0, height: 80,
              background: 'linear-gradient(to bottom, transparent, rgba(4,1,1,0.97))',
              pointerEvents: 'none',
              opacity: heroExpanded ? 0 : 1,
              transition: 'opacity 0.3s ease',
            }} />
          </div>
        </div>
      )}

      {/* Agent cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
        {rest.map((k, i) => (
          <div key={k} style={{ gridColumn: expanded === k ? '1 / -1' : 'auto', transition: 'grid-column 0.1s' }}>
            <SummaryCard
              node={nodeMap[k]!}
              expanded={expanded === k}
              onToggle={() => toggle(k)}
              cardRef={el => { cardRefs.current[k] = el }}
            />
          </div>
        ))}
      </div>
    </motion.div>
  )
}
