'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import AgentGraph from '@/components/AgentGraph'

const API = 'http://localhost:8000'

const AGENTS: Record<string, { label: string; role: string; description: string; icon: string; color: string }> = {
  explorer:         { label: 'Explorer',        role: 'Data Scout',        description: 'Scans dataset structure, file formats, and surface-level patterns to build a complete picture.',          icon: '◉', color: '#7c6fcd' },
  skeptic:          { label: 'Skeptic',          role: 'Quality Guard',     description: 'Challenges every assumption and flags data anomalies, inconsistencies, and quality issues.',             icon: '⚠', color: '#d46b8a' },
  statistician:     { label: 'Statistician',     role: 'Numbers Expert',    description: 'Computes distributions, correlations, significance tests and full statistical summaries.',              icon: '∑', color: '#4a9fd4' },
  feature_engineer: { label: 'Feature Engineer', role: 'Signal Extractor',  description: 'Identifies predictive features, transformations, and encoding strategies for maximum performance.',    icon: '⟁', color: '#3db87a' },
  ethicist:         { label: 'Ethicist',         role: 'Bias Detector',     description: 'Evaluates fairness, bias risks, and ethical implications across the dataset and model.',               icon: '⚖', color: '#d4874a' },
  pragmatist:       { label: 'Pragmatist',       role: 'Reality Check',     description: 'Balances complexity vs. feasibility and ensures the plan is actionable in the real world.',            icon: '◈', color: '#c4a832' },
  devil_advocate:   { label: 'Devil Advocate',   role: 'Critical Thinker',  description: 'Argues against prevailing conclusions to stress-test ideas and surface hidden failure modes.',         icon: '⛧', color: '#e63030' },
  optimizer:        { label: 'Optimizer',        role: 'Efficiency Expert', description: 'Identifies hyperparameter strategies, ensemble methods, and performance optimization paths.',          icon: '⚡', color: '#8a7cd4' },
  architect:        { label: 'Architect',        role: 'System Designer',   description: 'Designs overall model architecture and end-to-end pipeline structure.',                                icon: '⬡', color: '#a86cd4' },
  storyteller:      { label: 'Storyteller',      role: 'Insight Narrator',  description: 'Synthesises all findings into coherent narratives and final actionable reports.',                      icon: '✦', color: '#d4a8c4' },
}

const ALL_AGENTS = Object.keys(AGENTS)

const PHASES = [
  { id: 'discovery',      label: 'Discovery',          short: 'DSC' },
  { id: 'understanding',  label: 'Data Understanding', short: 'P1' },
  { id: 'design',         label: 'Model Design',       short: 'P2' },
  { id: 'generation',     label: 'Code Generation',    short: 'P3' },
  { id: 'complete',       label: 'Complete',            short: '✓' },
]

function phaseIndex(phase: string): number {
  const l = phase.toLowerCase()
  if (l.includes('complete'))                              return 4
  if (l.includes('code') || l.includes('generation') || l.includes('phase 3')) return 3
  if (l.includes('design') || l.includes('phase 2'))       return 2
  if (l.includes('understand') || l.includes('phase 1'))   return 1
  if (l.includes('discovery'))                              return 0
  if (l.includes('initializ'))                              return -1
  return -1
}

function parsePhaseLabel(phase: string): string {
  const l = phase.toLowerCase()
  if (l.includes('understand') || l.includes('phase 1')) return 'Data Understanding'
  if (l.includes('design')     || l.includes('phase 2')) return 'Model Design'
  if (l.includes('code') || l.includes('generation') || l.includes('phase 3')) return 'Code Generation'
  if (l.includes('discovery'))                            return 'Discovery'
  if (l.includes('initializ'))                            return 'Initialising'
  return phase.charAt(0).toUpperCase() + phase.slice(1).toLowerCase()
}

function logColor(line: string): string {
  if (line.includes('✅') || line.includes('SUCCESS')) return '#34d399'
  if (line.includes('❌') || line.includes('ERROR'))   return '#f87171'
  if (line.includes('⚠') || line.includes('WARNING')) return '#f59e0b'
  if (line.includes('Phase'))                           return 'rgba(255,255,255,0.65)'
  if (line.includes('[') && line.includes(']'))         return 'rgba(255,255,255,0.4)'
  return 'rgba(255,255,255,0.25)'
}

type ViewMode = 'grid' | 'split' | 'log' | 'graph'

// Agent card
function AgentCard({ name, isCurrent, isDone }: { name: string; isCurrent: boolean; isDone: boolean }) {
  const a = AGENTS[name]
  if (!a) return null
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      style={{
        padding: '13px 15px', borderRadius: 13, position: 'relative', overflow: 'hidden',
        background: isDone   ? 'rgba(52,211,153,0.06)'
                  : isCurrent ? `${a.color}0f`
                  : 'rgba(255,255,255,0.02)',
        backdropFilter: 'blur(12px)',
        border: `1px solid ${isDone ? 'rgba(52,211,153,0.22)' : isCurrent ? `${a.color}35` : 'rgba(255,255,255,0.05)'}`,
        boxShadow: isCurrent ? `0 0 20px ${a.color}15` : 'none',
        transition: 'all 0.4s ease',
      }}
    >
      {isCurrent && (
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, overflow: 'hidden' }}>
          <motion.div
            style={{ height: '100%', width: '40%', background: `linear-gradient(90deg, transparent, ${a.color}, transparent)` }}
            animate={{ x: ['-100%', '350%'] }}
            transition={{ repeat: Infinity, duration: 1.8, ease: 'linear' }}
          />
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 9, flexShrink: 0,
          background: isDone ? 'rgba(52,211,153,0.1)' : `${a.color}15`,
          border: `1px solid ${isDone ? 'rgba(52,211,153,0.25)' : `${a.color}28`}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, color: isDone ? '#34d399' : a.color,
        }}>
          {isDone ? '✓' : a.icon}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12.5, fontWeight: 600, color: isDone ? '#34d399' : isCurrent ? a.color : 'rgba(255,255,255,0.35)', transition: 'color 0.3s' }}>
              {a.label}
            </span>
            {isCurrent && (
              <span style={{ display: 'flex', gap: 2.5 }}>
                {[0,1,2].map(i => <span key={i} style={{ width: 3.5, height: 3.5, borderRadius: '50%', background: a.color, display: 'inline-block', animation: `pulse-dot 1.2s ${i*0.2}s ease infinite` }} />)}
              </span>
            )}
          </div>
          <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.2)', marginTop: 1 }}>{a.role}</div>
        </div>
      </div>
    </motion.div>
  )
}

// Agent popup
function AgentPopup({ name }: { name: string }) {
  const a = AGENTS[name]
  if (!a) return null
  return (
    <motion.div
      key={name}
      initial={{ opacity: 0, y: 24, scale: 0.94 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 12, scale: 0.96 }}
      transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
      style={{
        position: 'fixed', bottom: 28, right: 28, zIndex: 60,
        width: 300,
        background: 'rgba(6,2,2,0.72)',
        backdropFilter: 'blur(28px)',
        border: `1px solid ${a.color}38`,
        borderRadius: 18, overflow: 'hidden',
        boxShadow: `0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px ${a.color}12, 0 8px 32px ${a.color}14`,
      }}
    >
      <div style={{ height: 2, background: `linear-gradient(90deg, ${a.color}, ${a.color}30)` }} />
      <div style={{ padding: '16px 18px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div style={{
            width: 42, height: 42, borderRadius: 11, flexShrink: 0,
            background: `${a.color}12`, border: `1px solid ${a.color}35`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 19, color: a.color, boxShadow: `0 0 18px ${a.color}25`,
          }}>
            {a.icon}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 15, color: a.color }}>{a.label}</div>
            <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.28)', marginTop: 1 }}>{a.role}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: a.color, display: 'inline-block', animation: 'pulse-dot 1.4s ease infinite', boxShadow: `0 0 7px ${a.color}` }} />
            <span style={{ fontSize: 9.5, color: a.color, fontFamily: "'JetBrains Mono',monospace", letterSpacing: '0.08em' }}>LIVE</span>
          </div>
        </div>
        <div style={{ height: 1, background: `${a.color}15`, marginBottom: 12 }} />
        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.38)', lineHeight: 1.65 }}>{a.description}</p>
        <div style={{ marginTop: 14, height: 2, borderRadius: 2, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
          <motion.div
            style={{ height: '100%', width: '35%', background: `linear-gradient(90deg, transparent, ${a.color}, transparent)` }}
            animate={{ x: ['-100%', '400%'] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
          />
        </div>
      </div>
    </motion.div>
  )
}

// Log panel component
function LogPanel({ logLines, logRef }: { logLines: string[]; logRef: React.RefObject<HTMLDivElement> }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.15)', fontFamily: "'JetBrains Mono',monospace" }}>$</span>
          <span style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.25)', fontFamily: "'JetBrains Mono',monospace", letterSpacing: '0.1em' }}>LIVE LOG</span>
        </div>
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.15)', fontFamily: "'JetBrains Mono',monospace" }}>{logLines.length} lines</span>
      </div>
      <div ref={logRef} style={{ flex: 1, overflow: 'auto', padding: '10px 18px', display: 'flex', flexDirection: 'column', gap: 1 }}>
        {logLines.map((line, i) => (
          <div key={i} style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10.5, color: logColor(line), lineHeight: 1.75, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{line}</div>
        ))}
      </div>
    </div>
  )
}

export default function RunPage() {
  const { id }   = useParams<{ id: string }>()
  const router   = useRouter()
  const [phase,        setPhase]        = useState('Initialising')
  const [activeAgent,  setActiveAgent]  = useState('')
  const [activeAgents, setActiveAgents] = useState<string[]>([])
  const [doneAgents,   setDoneAgents]   = useState<string[]>([])
  const [done,         setDone]         = useState(false)
  const [error,        setError]        = useState('')
  const [logLines,     setLogLines]     = useState<string[]>([])
  const [viewMode,     setViewMode]     = useState<ViewMode>('graph')
  const cursorRef = useRef(0); const doneRef = useRef(false)
  const timerRef  = useRef<NodeJS.Timeout | null>(null)
  const linesRef  = useRef<string[]>([])
  const logRef    = useRef<HTMLDivElement>(null)

  const currentPhaseIdx = phaseIndex(phase)

  const poll = useCallback(async () => {
    if (doneRef.current) return
    try {
      const r = await fetch(`${API}/api/poll/${id}?cursor=${cursorRef.current}`)
      const d = await r.json()
      if (d.lines?.length) { linesRef.current = [...linesRef.current, ...d.lines].slice(-600); setLogLines([...linesRef.current]) }
      cursorRef.current = d.cursor ?? cursorRef.current
      if (d.phase) setPhase(parsePhaseLabel(d.phase))
      if (d.agent) setActiveAgent(d.agent.toLowerCase().replace(/['\s]+/g,'_').replace(/[^a-z_]/g,''))
      if (d.everActive?.length) setActiveAgents((d.everActive as string[]).map((a:string) => a.toLowerCase().replace(/['\s]+/g,'_').replace(/[^a-z_]/g,'')))
      if (d.done) {
        doneRef.current = true; setDone(true)
        if (d.error) setError(d.error)
        else { setPhase('Complete'); setDoneAgents(prev => [...new Set([...prev, ...activeAgents])]); setTimeout(() => router.push(`/results/${id}`), 2500) }
      }
    } catch {}
    if (!doneRef.current) timerRef.current = setTimeout(poll, 1500)
  }, [id, router, activeAgents])

  useEffect(() => { poll(); return () => { if (timerRef.current) clearTimeout(timerRef.current) } }, [poll])
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [logLines])

  const progress = doneAgents.length / ALL_AGENTS.length

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>

      {/* Floating nav */}
      <div style={{
        position: 'fixed', top: 16, left: '50%', transform: 'translateX(-50%)',
        zIndex: 50, width: 'calc(100% - 48px)', maxWidth: 1200,
        background: 'rgba(6,2,2,0.65)', backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.07)', borderRadius: 13,
        padding: '11px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {/* Step workflow indicator */}
        <div className="step-track">
          {PHASES.map((p, i) => (
            <div key={p.id} style={{ display: 'flex', alignItems: 'center' }}>
              <div
                className={`step-node ${currentPhaseIdx > i ? 'done' : currentPhaseIdx === i ? 'active' : ''}`}
                title={p.label}
              >
                {currentPhaseIdx > i ? '✓' : p.short}
              </div>
              {i < PHASES.length - 1 && (
                <div className={`step-connector ${currentPhaseIdx > i ? 'done' : currentPhaseIdx === i ? 'active' : ''}`} />
              )}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* View mode toggle */}
          <div className="view-toggle">
            <button className={viewMode === 'grid' ? 'active' : ''} onClick={() => setViewMode('grid')}>Grid</button>
            <button className={viewMode === 'split' ? 'active' : ''} onClick={() => setViewMode('split')}>Split</button>
            <button className={viewMode === 'log' ? 'active' : ''} onClick={() => setViewMode('log')}>Log</button>
            <button className={viewMode === 'graph' ? 'active' : ''} onClick={() => setViewMode('graph')}>Graph</button>
          </div>
          <button className="btn-ghost" onClick={() => router.push('/')} style={{ fontSize: 11, padding: '5px 12px' }}>← Home</button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', paddingTop: 76 }}>

        {/* Agent grid area — visible in grid & split modes */}
        {(viewMode === 'grid' || viewMode === 'split') && (
          <div style={{ flex: 1, padding: '28px 32px', overflowY: 'auto' }}>

            {/* Stats row */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
              {[
                { label: 'Run', value: id },
                { label: 'Phase', value: phase },
                { label: 'Active', value: `${activeAgents.length} agents` },
                { label: 'Done', value: `${doneAgents.length} / ${ALL_AGENTS.length}` },
              ].map(s => (
                <div key={s.label} style={{
                  padding: '8px 14px', borderRadius: 10,
                  background: 'rgba(255,255,255,0.02)',
                  backdropFilter: 'blur(12px)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div className="label" style={{ marginBottom: 3 }}>{s.label}</div>
                  <div style={{ fontSize: 12.5, fontFamily: "'JetBrains Mono',monospace", color: 'rgba(255,255,255,0.6)', whiteSpace: 'nowrap', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.value}</div>
                </div>
              ))}
            </div>

            {/* Progress bar */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span className="label">Progress</span>
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', fontFamily: "'JetBrains Mono',monospace" }}>
                  {done ? 'COMPLETE' : `${Math.round(progress * 100)}%`}
                </span>
              </div>
              <div style={{ height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.04)', overflow: 'hidden' }}>
                <motion.div
                  style={{ height: '100%', borderRadius: 4, background: done ? '#34d399' : 'linear-gradient(90deg, #e63030, #ff5555)' }}
                  animate={{ width: `${done ? 100 : Math.max(2, progress * 100)}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </div>

            {/* Agent cards */}
            <div className="label" style={{ marginBottom: 12 }}>Agents</div>
            <motion.div layout style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 9 }}>
              {ALL_AGENTS.map(name => (
                <AgentCard key={name} name={name} isCurrent={activeAgent === name} isDone={doneAgents.includes(name)} />
              ))}
            </motion.div>

            {/* Done */}
            <AnimatePresence>
              {done && !error && (
                <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                  style={{ marginTop: 28, padding: '20px 24px', borderRadius: 14, background: 'rgba(52,211,153,0.06)', backdropFilter: 'blur(16px)', border: '1px solid rgba(52,211,153,0.18)', display: 'flex', alignItems: 'center', gap: 14 }}>
                  <span style={{ fontSize: 26, color: '#34d399' }}>✦</span>
                  <div>
                    <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 16, color: '#34d399' }}>Analysis Complete</div>
                    <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>Loading results…</div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error */}
            <AnimatePresence>
              {error && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  style={{ marginTop: 24, padding: '18px 22px', borderRadius: 14, background: 'rgba(230,48,48,0.06)', backdropFilter: 'blur(16px)', border: '1px solid rgba(230,48,48,0.22)' }}>
                  <div style={{ fontSize: 13, color: '#f87171', fontWeight: 600, marginBottom: 10 }}>Pipeline Failed</div>
                  <pre style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 180, overflow: 'auto', fontFamily: "'JetBrains Mono',monospace" }}>{error}</pre>
                  <button className="btn-ghost" onClick={() => router.push('/')} style={{ marginTop: 12, fontSize: 12 }}>← Return Home</button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Graph panel — full-screen force-directed agent graph */}
        {viewMode === 'graph' && (
          <div style={{ flex: 1, height: 'calc(100vh - 76px)', overflow: 'hidden' }}>
            <AgentGraph activeAgent={activeAgent} doneAgents={doneAgents} done={done} />
          </div>
        )}

        {/* Log panel — visible in split & log modes */}
        {(viewMode === 'split' || viewMode === 'log') && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: viewMode === 'log' ? '100%' : 400, opacity: 1 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            style={{
              borderLeft: viewMode === 'split' ? '1px solid rgba(255,255,255,0.05)' : 'none',
              background: 'rgba(4,1,1,0.7)', backdropFilter: 'blur(16px)',
              display: 'flex', flexDirection: 'column', overflow: 'hidden',
            }}
          >
            <LogPanel logLines={logLines} logRef={logRef} />
          </motion.div>
        )}
      </div>

      {/* Agent popup */}
      <AnimatePresence mode="wait">
        {activeAgent && !done && viewMode !== 'log' && viewMode !== 'graph' && <AgentPopup key={activeAgent} name={activeAgent} />}
      </AnimatePresence>
    </div>
  )
}
