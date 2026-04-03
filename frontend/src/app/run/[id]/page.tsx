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

function buildNodes(entries: { agent: string; role: string; content: string }[]): NodeData[] {
  const contentMap = new Map<string, string>()
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
            if (data.entries) setNodes(buildNodes(data.entries))
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
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, background: 'radial-gradient(ellipse at 40% 50%, #0c0818 0%, #06020e 55%, #030008 100%)' }} />

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
              background: '#0c0c0c',
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
                  onClick={() => setSelectedNode(null)}
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
function extractBullets(content: string, max = 4): string[] {
  const lines = content.split('\n')
  const bullets: string[] = []
  for (const line of lines) {
    const m = line.match(/^[-*•]\s+(.+)/) ?? line.match(/^\d+\.\s+(.+)/)
    if (m) { bullets.push(m[1].trim()); if (bullets.length >= max) break }
  }
  if (bullets.length === 0) {
    const plain = content.replace(/#+\s[^\n]*/g, '').trim()
    const sentence = plain.split(/\.\s+/)[0]
    if (sentence) bullets.push(sentence.trim())
  }
  return bullets
}

function SummaryCard({ node, bullets }: { node: NodeData; bullets: string[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      style={{
        padding: '18px 20px', borderRadius: 16,
        background: 'rgba(8,2,2,0.55)', backdropFilter: 'blur(18px)',
        border: `1px solid ${node.color}18`, position: 'relative', overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg, ${node.color}, transparent)` }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{ width: 34, height: 34, borderRadius: 10, background: `${node.color}14`, border: `1px solid ${node.color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, color: node.color, flexShrink: 0 }}>{node.icon}</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: node.color }}>{node.label}</div>
          <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.25)' }}>{node.role}</div>
        </div>
      </div>
      <ul style={{ margin: 0, paddingLeft: 16 }}>
        {bullets.map((b, i) => (
          <li key={i} style={{ fontSize: 12, color: 'rgba(255,255,255,0.55)', lineHeight: 1.65, marginBottom: 4, fontFamily: "'Inter',sans-serif" }}>{b}</li>
        ))}
      </ul>
    </motion.div>
  )
}

const SUMMARY_ORDER = ['storyteller', 'statistician', 'skeptic', 'ethicist', 'optimizer', 'architect', 'devil_advocate', 'feature_engineer', 'explorer', 'pragmatist']

function SummaryView({ nodes }: { nodes: NodeData[] }) {
  const nodeMap = Object.fromEntries(nodes.map(n => [n.key, n]))
  const hero     = nodeMap['storyteller'] ?? nodes.find(n => n.content)
  const heroLines = hero ? extractBullets(hero.content, 5) : []
  const rest     = SUMMARY_ORDER.filter(k => k !== 'storyteller' && nodeMap[k]?.content)

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ padding: '12px 32px 60px' }}>
      {hero && hero.content && (
        <div style={{ marginBottom: 24, padding: '24px 28px', borderRadius: 18, background: `${hero.color}08`, border: `1px solid ${hero.color}25`, position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg, ${hero.color}, ${hero.color}33)` }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
            <div style={{ width: 48, height: 48, borderRadius: 14, background: `${hero.color}18`, border: `1px solid ${hero.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: hero.color }}>{hero.icon}</div>
            <div>
              <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 17, color: hero.color }}>{hero.label}</div>
              <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>Key Takeaways</div>
            </div>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {heroLines.map((b, i) => <li key={i} style={{ fontSize: 13.5, color: 'rgba(255,255,255,0.7)', lineHeight: 1.7, marginBottom: 6 }}>{b}</li>)}
          </ul>
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
        {rest.map((k, i) => (
          <motion.div key={k} transition={{ delay: i * 0.04 }}>
            <SummaryCard node={nodeMap[k]!} bullets={extractBullets(nodeMap[k]!.content, 4)} />
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}
