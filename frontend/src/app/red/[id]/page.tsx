'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import GlobalBackground from '@/components/GlobalBackground'
import RedModeGraph, { PERSONA_COLORS, P1_META, P1_ORDER } from '@/components/RedModeGraph'
import {
  MOCK_PERSONAS,
  MOCK_GROUPS,
  MOCK_GROUP_ORDER,
  MOCK_PANEL_OUTPUTS,
  MOCK_CHAMPION_DEBATE,
  MOCK_SYNTHESIS,
} from '@/lib/mockRedMode'

const API = 'http://localhost:8000'
const POLL_MS = 1500

interface GroupResult {
  label:        string
  members:      string[]
  panel_output: string
  champion:     string
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
  const [phase,        setPhase]        = useState<'phase1' | 'groups' | 'champions' | 'synthesis'>('phase1')
  const [phase1Agents, setPhase1Agents] = useState<string[]>([])
  const [activeAgent,  setActiveAgent]  = useState('')

  // Tournament state
  const [lastLine,       setLastLine]       = useState('')
  const [activeGroup,    setActiveGroup]    = useState('')
  const [doneGroups,     setDoneGroups]     = useState<string[]>([])
  const [groupChampions, setGroupChampions] = useState<Record<string, string>>({})
  const [activePersona,  setActivePersona]  = useState('')
  const [donePersonas,   setDonePersonas]   = useState<string[]>([])
  const [synthesisDone,  setSynthesisDone]  = useState(false)
  const [done,           setDone]           = useState(false)
  const [error,          setError]          = useState('')
  const [result,         setResult]         = useState<RedResult | null>(null)

  // Panel state
  const [selectedPersona, setSelectedPersona] = useState<string>('')
  const [selectedGroup,   setSelectedGroup]   = useState<string>('')
  const [activeTab,       setActiveTab]       = useState<'panel' | 'champion' | 'synthesis'>('panel')

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

      // ── Stage A: Group Panel Debates ────────────────────────────
      setLastLine('STAGE A — Group Panel Debates')
      const finishedGroups: string[] = []
      const champions: Record<string, string> = {}
      for (const gk of MOCK_GROUP_ORDER) {
        if (cancelled) return
        const group = MOCK_GROUPS[gk]
        setActiveGroup(gk)
        // Mark all members as active
        for (const member of group.members) {
          setActivePersona(member)
          await delay(100)
        }
        setLastLine(`${group.label} — ${group.members.length} experts debating`)
        await delay(800)
        if (cancelled) return
        // Mark all members as done
        setDonePersonas(prev => [...prev, ...group.members])
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
        setActivePersona(champ)
        setLastLine(`${champ.replace(/_/g, ' ')} entering cross-debate`)
        await delay(600)
        if (cancelled) return
      }

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
            label: MOCK_GROUPS[gk].label,
            members: MOCK_GROUPS[gk].members,
            panel_output: MOCK_PANEL_OUTPUTS[gk],
            champion: MOCK_GROUPS[gk].champion,
          }])
        ),
        champions: Object.values(MOCK_GROUPS).map(g => g.champion),
        champion_debate: MOCK_CHAMPION_DEBATE,
        synthesis: MOCK_SYNTHESIS,
      })
      setActiveTab('panel')
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
      if (data.phase !== 'phase1' && data.agent) setActivePersona(data.agent)
      if (data.activeGroup)         setActiveGroup(data.activeGroup)
      if (data.doneGroups)          setDoneGroups(data.doneGroups)
      if (data.groupChampions)      setGroupChampions(data.groupChampions)
      if (data.everActive)          setDonePersonas(data.everActive)
      if (data.synthesisDone)       setSynthesisDone(data.synthesisDone)

      if (data.done) {
        setDone(true)
        const res2   = await fetch(`${API}/api/red-mode/result/${id}`)
        const result = await res2.json()
        if (!result.error) {
          setResult(result)
          setActiveTab('panel')
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
    groups:    'Stage A — Group Panels',
    champions: 'Stage B — Champions',
    synthesis: 'Stage C — Synthesis',
  }

  // Panel open logic
  const panelOpen    = !!selectedPersona || !!selectedGroup || activeTab === 'synthesis'
  const panelColor   = selectedPersona ? (PERSONA_COLORS[selectedPersona] ?? '#e11d48') : '#e11d48'

  const closePanel = () => { setSelectedPersona(''); setSelectedGroup(''); setActiveTab('panel') }

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
          {/* Synthesis button */}
          {result?.synthesis && (
            <button
              onClick={() => { setSelectedPersona(''); setSelectedGroup(''); setActiveTab('synthesis') }}
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
          {/* Stage label */}
          {phase === 'phase1' ? (
            <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', padding: '3px 10px', borderRadius: 6, color: '#ffffff', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.2)' }}>
              Phase 1 — {phase1Agents.length}/9 agents
            </span>
          ) : phase !== 'phase1' && (
            <span style={{
              fontSize: 10, fontFamily: 'JetBrains Mono', padding: '3px 10px', borderRadius: 6,
              color: '#dc2626',
              background: 'rgba(220,38,38,0.07)', border: '1px solid rgba(220,38,38,0.18)',
            }}>
              {stageLabel[phase] ?? phase}
            </span>
          )}
          {/* Group progress */}
          {phase === 'groups' && (
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>
              {doneGroups.length}/4 groups
            </span>
          )}
          {phase === 'champions' && (
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.18)', fontFamily: 'JetBrains Mono' }}>
              {championsSet.size} champions
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

        {/* Graph */}
        <div style={{ position: 'absolute', inset: 0 }}>
          <RedModeGraph
            personas={personas}
            activePersona={activePersona}
            donePersonas={donePersonas}
            champions={Object.values(groupChampions)}
            stage={phase}
            synthesisDone={synthesisDone}
            onSelectPersona={p => {
              if (p) {
                setSelectedPersona(p)
                setSelectedGroup('')
                // Auto-select tab based on whether this persona is a champion
                setActiveTab(championsSet.has(p) && result?.champion_debate?.[p] ? 'champion' : 'panel')
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
                  <button onClick={() => setActiveTab('panel')} style={{
                    padding: '5px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
                    fontFamily: 'JetBrains Mono',
                    background: activeTab === 'panel' ? `${panelColor}18` : 'transparent',
                    border: `1px solid ${activeTab === 'panel' ? panelColor + '88' : 'rgba(255,255,255,0.08)'}`,
                    color: activeTab === 'panel' ? panelColor : 'rgba(255,255,255,0.3)',
                    transition: 'all 0.15s',
                  }}>
                    Group Panel
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
                    ) : activeTab === 'panel' && selectedPersona ? (
                      <div style={{ padding: '16px 20px' }}>
                        {(() => {
                          const gk = personaGroup(selectedPersona)
                          const panelText = gk ? result?.groups?.[gk]?.panel_output : null
                          if (panelText) return <Markdown text={panelText} />
                          return <div style={{ color: 'rgba(255,255,255,0.25)', fontSize: 12, padding: 16 }}>Waiting for group panel…</div>
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
