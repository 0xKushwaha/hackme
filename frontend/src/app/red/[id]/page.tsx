'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import RedModeGraph, { PERSONA_COLORS, P1_META, P1_ORDER } from '@/components/RedModeGraph'
import {
  MOCK_PERSONAS,
  MOCK_ROUND1,
  MOCK_ROUND2,
  MOCK_SYNTHESIS,
} from '@/lib/mockRedMode'

const API = 'http://localhost:8000'
const POLL_MS = 1500

interface RedResult {
  personas:  string[]
  round1:    Record<string, string>
  round2:    Record<string, string>
  synthesis: string
}

// ── Markdown renderer (same as run page) ─────────────────────────────
function Markdown({ text }: { text: string }) {
  const html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^### (.+)$/gm,  '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,   '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,    '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,    '<em>$1</em>')
    .replace(/`(.+?)`/g,      '<code>$1</code>')
    .replace(/^---$/gm,       '<hr/>')
    .replace(/^- (.+)$/gm,    '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, s => `<ul>${s}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[huli]|<\/[huli]|<p|<\/p|<hr)(.+)$/gm, '<p>$1</p>')
  return (
    <div
      className="report"
      style={{ lineHeight: 1.75, fontSize: 13.5, color: 'rgba(255,255,255,0.82)' }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}


export default function RedModePage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()

  // Phase 1 state
  const [phase,        setPhase]        = useState<'phase1' | 'debate'>('phase1')
  const [phase1Agents, setPhase1Agents] = useState<string[]>([])
  const [activeAgent,  setActiveAgent]  = useState('')   // active Phase 1 agent

  // Debate state
  const [lines,        setLines]        = useState<string[]>([])
  const [currentRound, setCurrentRound] = useState(0)
  const [roundPersonas,setRoundPersonas]= useState<Record<string, string[]>>({ '1': [], '2': [], '3': [] })
  const [synthesisDone,setSynthesisDone]= useState(false)
  const [activePersona,setActivePersona]= useState('')
  const [done,         setDone]         = useState(false)
  const [error,        setError]        = useState('')
  const [result,       setResult]       = useState<RedResult | null>(null)
  const [selectedPersona, setSelectedPersona] = useState<string>('')
  const [activeTab,    setActiveTab]    = useState<'r1' | 'r2' | 'synthesis'>('r1')

  const cursorRef = useRef(0)
  const pollRef   = useRef<ReturnType<typeof setTimeout>>()
  const isTest    = id.startsWith('test-')

  // ── Mock simulator (test mode) ────────────────────────────────────
  useEffect(() => {
    if (!isTest) return
    let cancelled = false
    const delay = (ms: number) => new Promise<void>(r => setTimeout(r, ms))

    const run = async () => {
      await delay(400)

      // ── Stage 1: Phase 1 agents ────────────────────────────────────
      setLines(prev => [...prev, '[RED_PHASE1_START]', '🔬 Phase 1 — Agents gathering analysis…'])
      const doneP1: string[] = []
      for (const agent of P1_ORDER) {
        if (cancelled) return
        setActiveAgent(agent)
        setLines(prev => [...prev, `[AGENT:${agent}]`])
        await delay(500)
        if (cancelled) return
        doneP1.push(agent)
        setPhase1Agents([...doneP1])
        setLines(prev => [...prev, `[AGENT_DONE:${agent}]`])
      }

      await delay(400)
      setLines(prev => [...prev, '[RED_PHASE1_DONE]', '✓ Phase 1 complete — starting debate'])
      setPhase('debate')
      setActiveAgent('')

      await delay(300)

      // ── Stage 2: Debate — Round 1 ─────────────────────────────────
      setCurrentRound(1)
      setLines(prev => [...prev, '[RED_ROUND:1]', 'ROUND 1 — Independent Takes (20 parallel calls)'])
      const doneR1: string[] = []
      for (const name of MOCK_PERSONAS) {
        if (cancelled) return
        setActivePersona(name)
        setLines(prev => [...prev, `[PERSONA:${name}]`])
        await delay(280)
        if (cancelled) return
        doneR1.push(name)
        setRoundPersonas(prev => ({ ...prev, '1': [...doneR1] }))
        setLines(prev => [...prev, `[PERSONA_DONE:${name}]`])
      }

      await delay(300)

      // Round 2
      setCurrentRound(2)
      setLines(prev => [...prev, '[RED_ROUND:2]', 'ROUND 2 — Full Debate (20 parallel calls)'])
      const doneR2: string[] = []
      for (const name of MOCK_PERSONAS) {
        if (cancelled) return
        setActivePersona(name)
        setLines(prev => [...prev, `[PERSONA:${name}]`])
        await delay(260)
        if (cancelled) return
        doneR2.push(name)
        setRoundPersonas(prev => ({ ...prev, '2': [...doneR2] }))
        setLines(prev => [...prev, `[PERSONA_DONE:${name}]`])
      }

      await delay(300)

      // Round 3 — synthesis
      setCurrentRound(3)
      setLines(prev => [...prev, '[RED_ROUND:3]', '[RED_SYNTHESIS]', 'Synthesising 20 takes across 2 rounds…'])
      await delay(1200)
      if (cancelled) return

      setSynthesisDone(true)
      setDone(true)
      setResult({ personas: MOCK_PERSONAS, round1: MOCK_ROUND1, round2: MOCK_ROUND2, synthesis: MOCK_SYNTHESIS })
      setActiveTab('synthesis')
      setSelectedPersona(MOCK_PERSONAS[0])
    }

    run()
    return () => { cancelled = true }
  }, [isTest, id])

  // ── Poll for live updates (real mode only) ────────────────────────
  const poll = useCallback(async () => {
    try {
      const res  = await fetch(`${API}/api/red-mode/poll/${id}?cursor=${cursorRef.current}`)
      const data = await res.json()

      if (data.error && data.done) { setError(data.error); return }

      cursorRef.current = data.cursor ?? cursorRef.current
      if (data.lines?.length)     setLines(prev => [...prev, ...data.lines])
      if (data.phase)             setPhase(data.phase)
      if (data.phase1Agents)      setPhase1Agents(data.phase1Agents)
      if (data.phase === 'phase1' && data.agent) setActiveAgent(data.agent)
      if (data.phase === 'debate' && data.agent) setActivePersona(data.agent)
      if (data.currentRound)      setCurrentRound(data.currentRound)
      if (data.roundPersonas)     setRoundPersonas(data.roundPersonas)
      if (data.synthesisDone)     setSynthesisDone(data.synthesisDone)

      if (data.done) {
        setDone(true)
        const res2   = await fetch(`${API}/api/red-mode/result/${id}`)
        const result = await res2.json()
        if (!result.error) {
          setResult(result)
          setActiveTab('synthesis')
          // Auto-select first persona for content pane
          if (result.personas?.length) setSelectedPersona(result.personas[0])
        } else {
          setError(result.error)
        }
        return
      }

      pollRef.current = setTimeout(poll, POLL_MS)
    } catch {
      pollRef.current = setTimeout(poll, POLL_MS * 2)
    }
  }, [id])

  useEffect(() => {
    if (isTest) return
    poll()
    return () => clearTimeout(pollRef.current)
  }, [poll, isTest])

  // ── Derived ───────────────────────────────────────────────────────
  // Always pass all 20 persona nodes so the graph is built once on mount.
  const ALL_HANDLES = MOCK_PERSONAS
  const personas    = result?.personas ?? ALL_HANDLES
  const doneR1      = roundPersonas['1'] ?? []
  const doneR2      = roundPersonas['2'] ?? []

  const displayName = (h: string) =>
    h.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  const roundLabel = ['', 'Round 1 — Takes', 'Round 2 — Debate', 'Round 3 — Synthesis']
  const roundColors = ['', '#dc2626', '#fb923c', '#f59e0b']

  // whether the floating content panel is open
  const panelOpen = !!selectedPersona || activeTab === 'synthesis'
  const panelPersona = selectedPersona
  const panelColor   = panelPersona ? (PERSONA_COLORS[panelPersona] ?? '#dc2626') : '#f59e0b'

  const closePanel = () => { setSelectedPersona(''); setActiveTab('r1') }

  return (
    <div style={{
      height: '100vh', overflow: 'hidden',
      background: 'linear-gradient(135deg, rgba(15,2,2,1) 0%, rgba(8,1,1,1) 100%)',
      color: '#f0f0f0', fontFamily: 'Inter, sans-serif',
      display: 'flex', flexDirection: 'column',
    }}>

      {/* ── Header ────────────────────────────────────────────────── */}
      <div style={{
        padding: '12px 24px', flexShrink: 0,
        borderBottom: '1px solid rgba(220,38,38,0.12)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(8,1,1,0.85)', backdropFilter: 'blur(20px)',
        zIndex: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', border: '1.5px solid #dc2626', flexShrink: 0 }} />
          <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: '#dc2626', fontWeight: 700, letterSpacing: '0.12em' }}>
            RED MODE
          </span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>{id}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {/* Synthesis button — shown when synthesis is ready */}
          {result?.synthesis && (
            <button
              onClick={() => { setSelectedPersona(''); setActiveTab('synthesis') }}
              style={{
                padding: '4px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 10,
                fontFamily: 'JetBrains Mono',
                background: activeTab === 'synthesis' ? 'rgba(220,38,38,0.18)' : 'rgba(220,38,38,0.06)',
                border: `1px solid ${activeTab === 'synthesis' ? 'rgba(220,38,38,0.55)' : 'rgba(220,38,38,0.2)'}`,
                color: '#dc2626', transition: 'all 0.15s',
              }}
            >
              ◎ Synthesis
            </button>
          )}
          {/* Phase label */}
          {phase === 'phase1' ? (
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', padding: '3px 10px', borderRadius: 6, color: '#38bdf8', background: 'rgba(56,189,248,0.07)', border: '1px solid rgba(56,189,248,0.2)' }}>
              Phase 1 — {phase1Agents.length}/9 agents
            </span>
          ) : currentRound > 0 && (
            <span style={{
              fontSize: 10, fontFamily: 'JetBrains Mono', padding: '3px 10px', borderRadius: 6,
              color: roundColors[currentRound] ?? '#dc2626',
              background: 'rgba(220,38,38,0.07)', border: '1px solid rgba(220,38,38,0.18)',
            }}>
              {roundLabel[currentRound] ?? ''}
            </span>
          )}
          {phase === 'debate' && (
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>
              {personas.length} personas
            </span>
          )}
          {done
            ? <span style={{ fontSize: 10, color: '#4ade80', fontFamily: 'JetBrains Mono' }}>✓ complete</span>
            : !error && <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#dc2626', display: 'inline-block', animation: 'pulse-dot 1.4s ease-in-out infinite' }} />
          }
          <button onClick={() => router.push('/')}
            style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: 17, padding: 0, lineHeight: 1 }}>
            ←
          </button>
        </div>
      </div>

      {/* ── Full-screen graph + floating overlays ─────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>

        {/* Unified graph — always visible, Phase 1 agents on left, personas on right */}
        <div style={{ position: 'absolute', inset: 0 }}>
          <RedModeGraph
            personas={personas}
            activePersona={activePersona}
            doneR1={doneR1}
            doneR2={doneR2}
            currentRound={currentRound}
            synthesisDone={synthesisDone}
            onSelectPersona={p => {
              if (p) { setSelectedPersona(p); setActiveTab('r1') }
              else   { setSelectedPersona('') }
            }}
            selectedPersona={selectedPersona}
            phase={phase}
            phase1Agents={phase1Agents}
            activeAgent={activeAgent}
          />
        </div>

        {/* ── Floating right content panel ──────────────────────── */}
        <AnimatePresence>
          {panelOpen && (
            <motion.div
              key="content-panel"
              initial={{ opacity: 0, x: 40 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 40 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              style={{
                position: 'absolute', top: 16, right: 16, bottom: 16,
                width: 460, zIndex: 15,
                background: 'rgba(8,1,1,0.93)', backdropFilter: 'blur(24px)',
                border: `1px solid ${panelColor}30`,
                borderRadius: 16, overflow: 'hidden',
                display: 'flex', flexDirection: 'column',
                boxShadow: `0 24px 64px rgba(0,0,0,0.7), 0 0 40px ${panelColor}12`,
              }}
            >
              {/* Panel top bar */}
              <div style={{ height: 2, background: `linear-gradient(90deg, ${panelColor}, transparent)`, flexShrink: 0 }} />

              {/* Panel header */}
              <div style={{
                padding: '14px 18px', flexShrink: 0,
                borderBottom: `1px solid ${panelColor}18`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {activeTab === 'synthesis' ? (
                    <>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: '#f59e0b' }}>◎</div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', fontFamily: "'Space Grotesk',sans-serif" }}>Synthesis</div>
                        <div style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.28)' }}>{personas.length} experts · {doneR2.length} debates</div>
                      </div>
                    </>
                  ) : panelPersona ? (
                    <>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: `${panelColor}18`, border: `1px solid ${panelColor}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: panelColor, fontFamily: "'JetBrains Mono',monospace" }}>
                        {panelPersona.split('_').map(w => w[0]?.toUpperCase()).join('').slice(0, 2)}
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: panelColor, fontFamily: "'Space Grotesk',sans-serif" }}>
                          {displayName(panelPersona)}
                        </div>
                        <div style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.28)' }}>
                          {doneR1.includes(panelPersona) ? '✓ R1' : 'R1 pending'}
                          {doneR2.includes(panelPersona) ? ' · ✓ R2' : ''}
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>
                <button
                  onClick={closePanel}
                  style={{ width: 26, height: 26, borderRadius: 7, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >✕</button>
              </div>

              {/* Tab switcher (persona view only) */}
              {activeTab !== 'synthesis' && panelPersona && (
                <div style={{ padding: '10px 18px 0', flexShrink: 0, display: 'flex', gap: 8 }}>
                  {(['r1', 'r2'] as const).map(tab => (
                    <button key={tab} onClick={() => setActiveTab(tab)} style={{
                      padding: '5px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
                      fontFamily: 'JetBrains Mono',
                      background: activeTab === tab ? `${panelColor}18` : 'transparent',
                      border: `1px solid ${activeTab === tab ? panelColor + '88' : 'rgba(255,255,255,0.08)'}`,
                      color: activeTab === tab ? panelColor : 'rgba(255,255,255,0.3)',
                      transition: 'all 0.15s',
                    }}>
                      {tab === 'r1' ? 'Round 1 — Initial Take' : 'Round 2 — Debate'}
                    </button>
                  ))}
                </div>
              )}

              {/* Scrollable content */}
              <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'thin' }}>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab + panelPersona}
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    {error ? (
                      <div style={{ padding: 24, color: '#fb7185' }}>
                        <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap' }}>{error}</pre>
                      </div>
                    ) : activeTab === 'synthesis' && result?.synthesis ? (
                      <div style={{ padding: '16px 20px' }}>
                        <Markdown text={result.synthesis} />
                      </div>
                    ) : panelPersona ? (
                      <div style={{ padding: '16px 20px' }}>
                        {activeTab === 'r1' && (result?.round1?.[panelPersona]
                          ? <Markdown text={result.round1[panelPersona]} />
                          : <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: 12, padding: 16 }}>Waiting for Round 1…</div>
                        )}
                        {activeTab === 'r2' && (result?.round2?.[panelPersona]
                          ? <Markdown text={result.round2[panelPersona]} />
                          : <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: 12, padding: 16 }}>Waiting for Round 2…</div>
                        )}
                      </div>
                    ) : null}
                  </motion.div>
                </AnimatePresence>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Live log ticker (bottom, during run) ──────────────── */}
        {!done && (
          <div style={{
            position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
            padding: '7px 18px',
            background: 'rgba(4,0,0,0.75)', backdropFilter: 'blur(8px)',
            borderTop: '1px solid rgba(220,38,38,0.08)',
          }}>
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: 'rgba(255,255,255,0.2)' }}>
              {phase === 'phase1'
                ? activeAgent ? `running ${P1_META[activeAgent]?.label ?? activeAgent}…` : 'Initialising Phase 1…'
                : lines[lines.length - 1] ?? 'Initialising…'
              }
            </span>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.75); }
        }
        .report h1 { font-size: 17px; font-weight: 700; color: #fff; margin: 20px 0 10px; }
        .report h2 { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.88); margin: 16px 0 8px; border-bottom: 1px solid rgba(220,38,38,0.18); padding-bottom: 6px; }
        .report h3 { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.75); margin: 13px 0 5px; }
        .report p  { color: rgba(255,255,255,0.7); margin-bottom: 10px; font-size: 13px; line-height: 1.72; }
        .report ul { padding-left: 20px; margin-bottom: 10px; }
        .report li { color: rgba(255,255,255,0.7); font-size: 13px; line-height: 1.7; margin-bottom: 4px; }
        .report strong { color: rgba(255,255,255,0.92); font-weight: 600; }
        .report em { color: rgba(255,255,255,0.5); font-style: italic; }
        .report code { background: rgba(220,38,38,0.1); color: #fca5a5; border: 1px solid rgba(220,38,38,0.2); border-radius: 4px; padding: 1px 5px; font-size: 11.5px; }
        .report hr { border: none; border-top: 1px solid rgba(220,38,38,0.14); margin: 14px 0; }
        .report blockquote { border-left: 2px solid rgba(220,38,38,0.35); padding-left: 12px; color: rgba(255,255,255,0.4); font-style: italic; margin: 10px 0; }
      `}</style>
    </div>
  )
}
