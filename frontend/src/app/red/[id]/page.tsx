'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import GlobalBackground from '@/components/GlobalBackground'
import RedModeGraph, { PERSONA_COLORS, P1_META, P1_ORDER } from '@/components/RedModeGraph'
import {
  MOCK_PERSONAS,
  MOCK_GROUPS,
  MOCK_GROUP_ORDER,
  MOCK_ROUND1_OUTPUTS,
  MOCK_ELECTION_OUTPUTS,
  MOCK_CHAMPION_DEBATE,
  MOCK_SYNTHESIS,
} from '@/lib/mockRedMode'

const API = 'http://localhost:8000'
const POLL_MS = 800

interface GroupResult {
  label:           string
  members:         string[]
  round1:          Record<string, string>
  election_output: string
  champion:        string
}

interface RedResult {
  personas:        string[]
  groups:          Record<string, GroupResult>
  champions:       string[]
  champion_debate: Record<string, string>
  synthesis:       string
}

// ── Markdown renderer ───────────────────────────────────────────────
function Markdown({ text }: { text: string }) {
  return (
    <div className="report" style={{ lineHeight: 1.75, fontSize: 13.5, color: 'rgba(255,255,255,0.82)' }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  )
}


export default function RedModePage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()

  // Phase 1 state
  const [phase,        setPhase]        = useState<'phase1' | 'groups' | 'election' | 'champions' | 'synthesis'>('phase1')
  const [phase1Agents, setPhase1Agents] = useState<string[]>([])
  const [activeAgent,  setActiveAgent]  = useState('')

  // Tournament state
  const [lastLine,        setLastLine]        = useState('')
  const [activeGroup,     setActiveGroup]     = useState('')
  const [doneGroups,      setDoneGroups]      = useState<string[]>([])
  const [groupChampions,  setGroupChampions]  = useState<Record<string, string>>({})
  const [activePersonas,  setActivePersonas]  = useState<string[]>([])
  const [donePersonas,    setDonePersonas]    = useState<string[]>([])
  const [synthesisDone,   setSynthesisDone]   = useState(false)
  const [done,           setDone]           = useState(false)
  const [error,          setError]          = useState('')
  const [result,         setResult]         = useState<RedResult | null>(null)

  // View state
  const [view, setView] = useState<'graph' | 'synthesis'>('graph')

  // Panel state
  const [selectedPersona, setSelectedPersona] = useState<string>('')
  const [selectedGroup,   setSelectedGroup]   = useState<string>('')
  const [activeTab,       setActiveTab]       = useState<'round1' | 'champion' | 'synthesis'>('round1')

  const [leaving, setLeaving] = useState(false)
  const goHome = useCallback(() => setLeaving(true), [])

  const downloadReport = useCallback(() => {
    if (!result) return
    const lines: string[] = []
    lines.push('# RED MODE — Tournament Debate Report\n')
    lines.push(`Run ID: ${id}\n`)
    lines.push('---\n')

    // ── Stage A: Group Round 1 ──────────────────────────────────
    lines.push('# STAGE A — Individual Persona Responses\n')
    for (const [gk, group] of Object.entries(result.groups)) {
      lines.push(`## Group: ${group.label}\n`)
      for (const [persona, response] of Object.entries(group.round1 ?? {})) {
        const name = persona.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        lines.push(`### ${name}\n\n${response}\n\n---\n`)
      }
      if (group.election_output) {
        lines.push(`### Election — Champion Selection\n\n${group.election_output}\n\n---\n`)
      }
    }

    // ── Stage B: Champion Cross-Debate ──────────────────────────
    lines.push('\n# STAGE B — Champion Cross-Debate\n')
    for (const [persona, response] of Object.entries(result.champion_debate ?? {})) {
      const name = persona.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
      lines.push(`## ${name} (Champion)\n\n${response}\n\n---\n`)
    }

    // ── Stage C: Final Synthesis ────────────────────────────────
    lines.push('\n# STAGE C — Final Synthesis & Verdict\n')
    lines.push(`${result.synthesis}\n`)

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `red_mode_debate_${id}.md`; a.click()
    URL.revokeObjectURL(url)
  }, [result, id])

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

      // ── Stage 1: Phase 1 agents ─────────────────────────────────
      setLastLine('🔬 Phase 1 — Agents gathering analysis…')
      const doneP1: string[] = []
      for (const agent of P1_ORDER) {
        if (cancelled) return
        setActiveAgent(agent)
        setLastLine(`running ${P1_META[agent]?.label ?? agent}…`)
        await delay(500)
        if (cancelled) return
        doneP1.push(agent)
        setPhase1Agents([...doneP1])
      }

      await delay(400)
      setLastLine('✓ Phase 1 complete — starting tournament debate')
      setPhase('groups')
      setActiveAgent('')

      await delay(300)

      // ── Stage A: Individual Persona Rounds ──────────────────────
      setLastLine('STAGE A — Individual Persona Round')
      const finishedGroups: string[] = []
      const champions: Record<string, string> = {}
      for (const gk of MOCK_GROUP_ORDER) {
        if (cancelled) return
        const group = MOCK_GROUPS[gk]
        setActiveGroup(gk)
        setPhase('groups')

        // Each persona responds independently, one at a time
        for (const member of group.members) {
          if (cancelled) return
          setActivePersonas([member])
          setLastLine(`${member.replace(/_/g, ' ')} responding…`)
          await delay(450)
          if (cancelled) return
          setDonePersonas(prev => [...prev, member])
        }

        // Election stage
        setActivePersonas([])
        setPhase('election')
        setLastLine(`${group.label} — electing champion…`)
        await delay(700)
        if (cancelled) return

        finishedGroups.push(gk)
        setDoneGroups([...finishedGroups])
        champions[gk] = group.champion
        setGroupChampions({ ...champions })
        setLastLine(`✓ ${group.label} — Champion: ${group.champion.replace(/_/g, ' ')}`)
        await delay(300)
      }

      await delay(300)

      // ── Stage B: Champion Cross-Debate ──────────────────────────
      setPhase('champions')
      setLastLine('STAGE B — Champion Cross-Debate')
      const champList = Object.values(champions)
      for (const champ of champList) {
        if (cancelled) return
        setActivePersonas([champ])
        setLastLine(`${champ.replace(/_/g, ' ')} entering cross-debate`)
        await delay(600)
        if (cancelled) return
      }
      setActivePersonas([])

      await delay(300)

      // ── Stage C: Synthesis ─────────────────────────────────────
      setPhase('synthesis')
      setLastLine('Synthesising tournament debate…')
      await delay(1200)
      if (cancelled) return

      setSynthesisDone(true)
      setDone(true)
      setResult({
        personas: MOCK_PERSONAS,
        groups: Object.fromEntries(
          MOCK_GROUP_ORDER.map(gk => [gk, {
            label:           MOCK_GROUPS[gk].label,
            members:         MOCK_GROUPS[gk].members,
            round1:          MOCK_ROUND1_OUTPUTS[gk] ?? {},
            election_output: MOCK_ELECTION_OUTPUTS[gk] ?? '',
            champion:        MOCK_GROUPS[gk].champion,
          }])
        ),
        champions: Object.values(MOCK_GROUPS).map(g => g.champion),
        champion_debate: MOCK_CHAMPION_DEBATE,
        synthesis: MOCK_SYNTHESIS,
      })
      setActiveTab('round1')
      setSelectedPersona('')
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
      if (data.lines?.length)       setLastLine(data.lines[data.lines.length - 1])
      if (data.phase)               setPhase(data.phase as typeof phase)
      if (data.phase1Agents)        setPhase1Agents(data.phase1Agents)
      if (data.phase === 'phase1' && data.agent) setActiveAgent(data.agent)
      if (data.activePersonas)      setActivePersonas(data.activePersonas)
      else if (data.phase !== 'phase1' && data.agent) setActivePersonas([data.agent])
      if (data.activeGroup)         setActiveGroup(data.activeGroup)
      if (data.doneGroups)          setDoneGroups(data.doneGroups)
      if (data.groupChampions)      setGroupChampions(data.groupChampions)
      if (data.donePersonas)        setDonePersonas(data.donePersonas)
      else if (data.everActive)     setDonePersonas(data.everActive)
      if (data.synthesisDone)       setSynthesisDone(data.synthesisDone)

      if (data.done) {
        setDone(true)
        const res2   = await fetch(`${API}/api/red-mode/result/${id}`)
        const result = await res2.json()
        if (!result.error) {
          setResult(result)
          setActiveTab('round1')
          setSelectedPersona('')
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
  const personas       = result?.personas ?? MOCK_PERSONAS
  const championsSet   = new Set(result?.champions ?? Object.values(groupChampions))

  const displayName = (h: string) =>
    h.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

  const stageLabel: Record<string, string> = {
    groups:    'Stage A — Individual Round',
    election:  'Stage A-elect — Champion Election',
    champions: 'Stage B — Champions',
    synthesis: 'Stage C — Synthesis',
  }

  // Panel open logic
  const panelOpen    = !!selectedPersona || !!selectedGroup || (activeTab === 'synthesis' && !!result?.synthesis)
  const panelColor   = selectedPersona ? (PERSONA_COLORS[selectedPersona] ?? '#e11d48') : '#e11d48'

  const closePanel = () => { setSelectedPersona(''); setSelectedGroup(''); setActiveTab('round1') }

  // Find which group a persona belongs to
  const personaGroup = (handle: string): string | null => {
    if (!result?.groups) return null
    for (const [gk, g] of Object.entries(result.groups)) {
      if (g.members.includes(handle)) return gk
    }
    return null
  }

  return (
    <div style={{
      height: '100vh', overflow: 'hidden',
      background: 'transparent',
      color: '#f0f0f0', fontFamily: 'Inter, sans-serif',
      display: 'flex', flexDirection: 'column',
      position: 'relative',
    }}>
      <GlobalBackground />

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
          {/* Graph / Synthesis tab switcher — shown once complete */}
          {done && !error && (
            <>
              {(['graph', 'synthesis'] as const).map(v => (
                <button key={v} onClick={() => setView(v)} style={{
                  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 0',
                  fontSize: 11, fontFamily: 'JetBrains Mono',
                  color: view === v ? '#dc2626' : 'rgba(255,255,255,0.35)',
                  borderBottom: view === v ? '1px solid #dc2626' : '1px solid transparent',
                  transition: 'all 0.15s', letterSpacing: '0.06em', textTransform: 'uppercase',
                }}>{v}</button>
              ))}
              <button onClick={downloadReport} style={{
                padding: '4px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 10,
                fontFamily: 'JetBrains Mono',
                background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.2)',
                color: '#dc2626', transition: 'all 0.15s',
              }}>↓ Report</button>
            </>
          )}
          {/* Stage label — only while running */}
          {!done && phase === 'phase1' && (
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', padding: '3px 10px', borderRadius: 6, color: '#ffffff', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.2)' }}>
              Phase 1 — {phase1Agents.length}/9 agents
            </span>
          )}
          {!done && phase !== 'phase1' && (
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', padding: '3px 10px', borderRadius: 6, color: '#dc2626', background: 'rgba(220,38,38,0.07)', border: '1px solid rgba(220,38,38,0.18)' }}>
              {stageLabel[phase] ?? phase}
            </span>
          )}
          {!done && (phase === 'groups' || phase === 'election') && (
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>
              {doneGroups.length}/4 groups
            </span>
          )}
          {!done && phase === 'champions' && (
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>
              {championsSet.size} champions
            </span>
          )}
          {done
            ? <span style={{ fontSize: 10, color: '#4ade80', fontFamily: 'JetBrains Mono' }}>✓ complete</span>
            : !error && <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#dc2626', display: 'inline-block', animation: 'pulse-dot 1.4s ease-in-out infinite' }} />
          }
          <button onClick={goHome}
            style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)', cursor: 'pointer', fontSize: 17, padding: 0, lineHeight: 1 }}>
            ←
          </button>
        </div>
      </div>

      {/* ── Full-screen graph + floating overlays ─────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>

        {/* Synthesis summary view */}
        {view === 'synthesis' && result && (
          <div style={{ position: 'absolute', inset: 0, overflowY: 'auto', zIndex: 5 }}>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ padding: '28px 32px 8px' }}>
              <h1 style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 22, letterSpacing: '-0.02em', color: '#fff' }}>
                Tournament Complete
              </h1>
              <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12.5, marginTop: 4 }}>
                {result.personas.length} experts · 4 groups · {result.champions.length} champions — run <span style={{ fontFamily: "'JetBrains Mono',monospace", color: 'rgba(255,255,255,0.4)' }}>{id}</span>
              </p>
            </motion.div>
            <RedSummaryView result={result} displayName={displayName} />
          </div>
        )}

        {/* Graph */}
        <div style={{ position: 'absolute', inset: 0, display: view === 'synthesis' ? 'none' : 'block' }}>
          <RedModeGraph
            personas={personas}
            activePersonas={activePersonas}
            donePersonas={donePersonas}
            champions={Object.values(groupChampions)}
            stage={phase}
            synthesisDone={synthesisDone}
            onSelectPersona={p => {
              if (p) {
                setSelectedPersona(p)
                setSelectedGroup('')
                // Auto-select tab based on whether this persona is a champion
                setActiveTab(championsSet.has(p) && result?.champion_debate?.[p] ? 'champion' : 'round1')
              } else {
                setSelectedPersona('')
              }
            }}
            onSelectSynthesis={() => {
               setSelectedPersona('')
               setSelectedGroup('')
               setActiveTab('synthesis')
            }}
            selectedPersona={selectedPersona}
            phase1Agents={phase1Agents}
            activeAgent={activeAgent}
            activeGroup={activeGroup}
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
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: 'rgba(225,29,72,0.15)', border: '1px solid rgba(225,29,72,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: '#e11d48' }}>◎</div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#e11d48', fontFamily: "'Space Grotesk',sans-serif" }}>Tournament Synthesis</div>
                        <div style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.28)' }}>{Object.keys(result?.groups ?? {}).length} groups · {result?.champions?.length ?? 0} champions</div>
                      </div>
                    </>
                  ) : selectedPersona ? (
                    <>
                      <div style={{ width: 32, height: 32, borderRadius: 9, background: `${panelColor}18`, border: `1px solid ${panelColor}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: panelColor, fontFamily: "'JetBrains Mono',monospace" }}>
                        {selectedPersona.split('_').map(w => w[0]?.toUpperCase()).join('').slice(0, 2)}
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: panelColor, fontFamily: "'Space Grotesk',sans-serif" }}>
                          {displayName(selectedPersona)}
                        </div>
                        <div style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.28)' }}>
                          {championsSet.has(selectedPersona) ? '★ Champion' : 'Panelist'}
                          {personaGroup(selectedPersona) ? ` · ${result?.groups?.[personaGroup(selectedPersona)!]?.label ?? ''}` : ''}
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
              {activeTab !== 'synthesis' && selectedPersona && (
                <div style={{ padding: '10px 18px 0', flexShrink: 0, display: 'flex', gap: 8 }}>
                  <button onClick={() => setActiveTab('round1')} style={{
                    padding: '5px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
                    fontFamily: 'JetBrains Mono',
                    background: activeTab === 'round1' ? `${panelColor}18` : 'transparent',
                    border: `1px solid ${activeTab === 'round1' ? panelColor + '88' : 'rgba(255,255,255,0.08)'}`,
                    color: activeTab === 'round1' ? panelColor : 'rgba(255,255,255,0.3)',
                    transition: 'all 0.15s',
                  }}>
                    Round 1
                  </button>
                  {championsSet.has(selectedPersona) && (
                    <button onClick={() => setActiveTab('champion')} style={{
                      padding: '5px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
                      fontFamily: 'JetBrains Mono',
                      background: activeTab === 'champion' ? `${panelColor}18` : 'transparent',
                      border: `1px solid ${activeTab === 'champion' ? panelColor + '88' : 'rgba(255,255,255,0.08)'}`,
                      color: activeTab === 'champion' ? panelColor : 'rgba(255,255,255,0.3)',
                      transition: 'all 0.15s',
                    }}>
                      ★ Champion Debate
                    </button>
                  )}
                </div>
              )}

              {/* Scrollable content */}
              <div style={{ flex: 1, overflowY: 'auto', scrollbarWidth: 'thin' }}>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeTab + selectedPersona}
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
                    ) : activeTab === 'champion' && selectedPersona && result?.champion_debate?.[selectedPersona] ? (
                      <div style={{ padding: '16px 20px' }}>
                        <Markdown text={result.champion_debate[selectedPersona]} />
                      </div>
                    ) : activeTab === 'round1' && selectedPersona ? (
                      <div style={{ padding: '16px 20px' }}>
                        {(() => {
                          const gk = personaGroup(selectedPersona)
                          const round1Text = gk ? result?.groups?.[gk]?.round1?.[selectedPersona] : null
                          if (round1Text) return <Markdown text={round1Text} />
                          return <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: 12, padding: 16 }}>Waiting for Round 1 response…</div>
                        })()}
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
                : lastLine || 'Initialising…'
              }
            </span>
          </div>
        )}
      </div>

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
        .report table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 12.5px; }
        .report th { background: rgba(220,38,38,0.12); color: rgba(255,255,255,0.85); font-weight: 600; padding: 8px 12px; text-align: left; border: 1px solid rgba(220,38,38,0.2); }
        .report td { padding: 7px 12px; border: 1px solid rgba(255,255,255,0.07); color: rgba(255,255,255,0.65); vertical-align: top; }
        .report tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
      `}</style>
    </div>
  )
}

// ── Red Mode Summary View ──────────────────────────────────────────────

function RedCard({
  title, subtitle, color, icon, content, expanded, onToggle, cardRef,
}: {
  title: string; subtitle: string; color: string; icon: string
  content: string; expanded: boolean; onToggle: () => void
  cardRef?: (el: HTMLDivElement | null) => void
}) {
  return (
    <div
      ref={cardRef}
      onClick={onToggle}
      style={{
        borderRadius: 16, cursor: 'pointer',
        background: expanded ? 'rgba(8,1,1,0.92)' : 'rgba(5,0,0,0.6)',
        backdropFilter: 'blur(18px)',
        border: `1px solid ${expanded ? color + '50' : color + '20'}`,
        position: 'relative', overflow: 'hidden',
        display: 'flex', flexDirection: 'column',
        boxShadow: expanded ? `0 0 0 1px ${color}20, 0 16px 48px rgba(0,0,0,0.5)` : 'none',
        transition: 'border-color 0.35s ease, background 0.35s ease, box-shadow 0.35s ease',
      }}
    >
      <div style={{ height: 2, background: `linear-gradient(90deg, ${color}, transparent)`, flexShrink: 0 }} />
      <div style={{ padding: '14px 18px 12px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: `1px solid ${color}15`, flexShrink: 0 }}>
        <div style={{ width: 32, height: 32, borderRadius: 9, background: `${color}14`, border: `1px solid ${color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color, flexShrink: 0 }}>{icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color }}>{title}</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>{subtitle}</div>
        </div>
        <div style={{ fontSize: 10, color: `${color}99`, fontFamily: 'JetBrains Mono', letterSpacing: '0.04em', flexShrink: 0 }}>
          {expanded ? '▲ collapse' : '▼ expand'}
        </div>
      </div>
      <div style={{ position: 'relative', overflow: 'hidden', maxHeight: expanded ? '9999px' : '260px', transition: expanded ? 'max-height 0.55s ease' : 'max-height 0.35s ease' }}>
        <div className="report" style={{ padding: '14px 20px 18px', fontSize: '0.82rem' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 64, background: 'linear-gradient(to bottom, transparent, rgba(5,0,0,0.97))', pointerEvents: 'none', opacity: expanded ? 0 : 1, transition: 'opacity 0.3s ease' }} />
      </div>
    </div>
  )
}

function RedSummaryView({ result, displayName }: { result: RedResult; displayName: (h: string) => string }) {
  const [expanded, setExpanded] = useState<string | null>('__synthesis__')
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({})

  const toggle = (key: string) => {
    const opening = expanded !== key
    setExpanded(opening ? key : null)
    if (opening) setTimeout(() => cardRefs.current[key]?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60)
  }

  const synthExpanded = expanded === '__synthesis__'

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ padding: '12px 32px 60px' }}>

      {/* ── Hero: Final Synthesis ──────────────────────────────── */}
      {result.synthesis && (
        <div
          ref={el => { cardRefs.current['__synthesis__'] = el }}
          onClick={() => toggle('__synthesis__')}
          style={{
            marginBottom: 20, borderRadius: 18, cursor: 'pointer',
            background: synthExpanded ? 'rgba(8,1,1,0.92)' : 'rgba(220,38,38,0.05)',
            border: `1px solid ${synthExpanded ? 'rgba(220,38,38,0.45)' : 'rgba(220,38,38,0.22)'}`,
            position: 'relative', overflow: 'hidden',
            boxShadow: synthExpanded ? '0 0 0 1px rgba(220,38,38,0.2), 0 16px 48px rgba(0,0,0,0.5)' : 'none',
            transition: 'border-color 0.35s ease, background 0.35s ease, box-shadow 0.35s ease',
          }}
        >
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: 'linear-gradient(90deg, #dc2626, rgba(220,38,38,0.2))' }} />
          <div style={{ padding: '20px 28px 14px', display: 'flex', alignItems: 'center', gap: 14, borderBottom: ' 1px solid rgba(220,38,38,0.18)' }}>
            <div style={{ width: 48, height: 48, borderRadius: 14, background: 'rgba(220,38,38,0.18)', border: '1px solid rgba(220,38,38,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22, color: '#dc2626', flexShrink: 0 }}>◎</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 17, color: '#dc2626' }}>Tournament Synthesis</div>
              <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>Stage C — Final Verdict</div>
            </div>
            <div style={{ fontSize: 11, color: 'rgba(220,38,38,0.6)', fontFamily: 'JetBrains Mono' }}>
              {synthExpanded ? '▲ collapse' : '▼ expand'}
            </div>
          </div>
          <div style={{ position: 'relative', overflow: 'hidden', maxHeight: synthExpanded ? '9999px' : '340px', transition: synthExpanded ? 'max-height 0.55s ease' : 'max-height 0.35s ease' }}>
            <div className="report" style={{ padding: '20px 28px 24px' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.synthesis}</ReactMarkdown>
            </div>
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 80, background: 'linear-gradient(to bottom, transparent, rgba(5,0,0,0.97))', pointerEvents: 'none', opacity: synthExpanded ? 0 : 1, transition: 'opacity 0.3s ease' }} />
          </div>
        </div>
      )}

      {/* ── Stage B: Champion Debate ───────────────────────────── */}
      {result.champions.length > 0 && Object.keys(result.champion_debate ?? {}).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: 'rgba(255,255,255,0.25)', letterSpacing: '0.1em', marginBottom: 12 }}>
            STAGE B — CHAMPION CROSS-DEBATE
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 14 }}>
            {result.champions.map(champ => {
              const response = result.champion_debate?.[champ]
              if (!response) return null
              const key = `champ_${champ}`
              const color = PERSONA_COLORS[champ] ?? '#e11d48'
              return (
                <div key={key} style={{ gridColumn: expanded === key ? '1 / -1' : 'auto' }}>
                  <RedCard
                    title={displayName(champ)}
                    subtitle="★ Champion — Cross-Debate"
                    color={color}
                    icon="★"
                    content={response}
                    expanded={expanded === key}
                    onToggle={() => toggle(key)}
                    cardRef={el => { cardRefs.current[key] = el }}
                  />
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Stage A: Group Round 1 ─────────────────────────────── */}
      {Object.entries(result.groups).map(([gk, group]) => {
        const members = Object.entries(group.round1 ?? {})
        if (!members.length && !group.election_output) return null
        return (
          <div key={gk} style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: 'rgba(255,255,255,0.25)', letterSpacing: '0.1em', marginBottom: 12 }}>
              STAGE A — {group.label.toUpperCase()}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 14 }}>
              {members.map(([persona, response]) => {
                const key = `r1_${persona}`
                const color = PERSONA_COLORS[persona] ?? '#e11d48'
                const isChamp = result.champions.includes(persona)
                return (
                  <div key={key} style={{ gridColumn: expanded === key ? '1 / -1' : 'auto' }}>
                    <RedCard
                      title={displayName(persona)}
                      subtitle={isChamp ? '★ Champion · Round 1' : 'Round 1 Response'}
                      color={color}
                      icon={isChamp ? '★' : persona.split('_').map(w => w[0]?.toUpperCase()).join('').slice(0, 2)}
                      content={response}
                      expanded={expanded === key}
                      onToggle={() => toggle(key)}
                      cardRef={el => { cardRefs.current[key] = el }}
                    />
                  </div>
                )
              })}
              {group.election_output && (() => {
                const key = `elect_${gk}`
                return (
                  <div key={key} style={{ gridColumn: expanded === key ? '1 / -1' : 'auto' }}>
                    <RedCard
                      title={`Champion Election`}
                      subtitle={`${group.label} · Judge's Analysis`}
                      color="rgba(245,158,11,1)"
                      icon="⚖"
                      content={group.election_output}
                      expanded={expanded === key}
                      onToggle={() => toggle(key)}
                      cardRef={el => { cardRefs.current[key] = el }}
                    />
                  </div>
                )
              })()}
            </div>
          </div>
        )
      })}
    </motion.div>
  )
}
