'use client'

import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

// ── Persona palette ───────────────────────────────────────────────────
export const PERSONA_COLORS: Record<string, string> = {
  andrej_karpathy:     '#e11d48',
  yann_lecun:          '#be123c',
  sam_altman:          '#f43f5e',
  geoffrey_hinton:     '#9f1239',
  francois_chollet:    '#e11d48',
  andrew_ng:           '#be123c',
  chip_huyen:          '#f43f5e',
  jeremy_howard:       '#fb7185',
  chris_olah:          '#e11d48',
  edward_yang:         '#be123c',
  ethan_mollick:       '#f43f5e',
  jay_alammar:         '#fb7185',
  jonas_mueller:       '#e11d48',
  lilian_weng:         '#be123c',
  matei_zaharia:       '#9f1239',
  santiago_valdarrama: '#e11d48',
  sebastian_raschka:   '#be123c',
  shreya_rajpal:       '#f43f5e',
  tim_dettmers:        '#fb7185',
  vicki_boykis:        '#e11d48',
}

const PERSONA_META: Record<string, { icon: string; role: string }> = {
  andrej_karpathy:     { icon: 'AK', role: 'Ex-Tesla AI Director'       },
  yann_lecun:          { icon: 'YL', role: 'Meta Chief AI Scientist'     },
  sam_altman:          { icon: 'SA', role: 'CEO, OpenAI'                 },
  geoffrey_hinton:     { icon: 'GH', role: 'Godfather of Deep Learning'  },
  francois_chollet:    { icon: 'FC', role: 'Creator of Keras'            },
  andrew_ng:           { icon: 'AN', role: 'Founder, DeepLearning.AI'    },
  chip_huyen:          { icon: 'CH', role: 'ML Systems Engineer'         },
  jeremy_howard:       { icon: 'JH', role: 'Founder, fast.ai'           },
  chris_olah:          { icon: 'CO', role: 'Interpretability Researcher' },
  edward_yang:         { icon: 'EY', role: 'PyTorch Core Developer'      },
  ethan_mollick:       { icon: 'EM', role: 'Wharton AI Professor'        },
  jay_alammar:         { icon: 'JA', role: 'ML Visualisation Expert'     },
  jonas_mueller:       { icon: 'JM', role: 'AutoML & Data Quality'       },
  lilian_weng:         { icon: 'LW', role: 'OpenAI Research Lead'        },
  matei_zaharia:       { icon: 'MZ', role: 'Co-creator of Apache Spark'  },
  santiago_valdarrama: { icon: 'SV', role: 'ML Engineer & Educator'      },
  sebastian_raschka:   { icon: 'SR', role: 'ML Researcher & Author'      },
  shreya_rajpal:       { icon: 'SR', role: 'AI Reliability Engineer'     },
  tim_dettmers:        { icon: 'TD', role: 'Quantization Researcher'     },
  vicki_boykis:        { icon: 'VB', role: 'ML Engineer & Writer'        },
}

export const P1_META: Record<string, { label: string; icon: string; color: string; role: string; description: string }> = {
  explorer:         { label: 'Explorer',      icon: '◉', color: '#a1a1aa', role: 'Data Scout',        description: 'Scans structure, finds patterns and key features.' },
  skeptic:          { label: 'Skeptic',       icon: '⚠', color: '#71717a', role: 'Quality Guard',     description: 'Challenges assumptions, flags anomalies and leakage.' },
  statistician:     { label: 'Statistician',  icon: '∑', color: '#d4d4d8', role: 'Numbers Expert',    description: 'Distributions, correlations, hypothesis testing.' },
  ethicist:         { label: 'Ethicist',      icon: '⚖', color: '#a1a1aa', role: 'Bias Detector',     description: 'Evaluates fairness and ethical implications.' },
  feature_engineer: { label: 'Feature Eng.',  icon: '⟁', color: '#e4e4e7', role: 'Signal Extractor',  description: 'New features, encodings, and transformations.' },
  pragmatist:       { label: 'Pragmatist',    icon: '◈', color: '#d4d4d8', role: 'Reality Check',     description: 'Model plan — which models, eval metric, split.' },
  devil_advocate:   { label: "Devil's Adv.",  icon: '⛧', color: '#71717a', role: 'Critical Thinker',  description: 'Stress-tests the plan, proposes alternatives.' },
  optimizer:        { label: 'Optimizer',     icon: '⚡', color: '#a1a1aa', role: 'Efficiency Expert', description: 'Hyperparameter tuning, CV strategy, ensembles.' },
  architect:        { label: 'Architect',     icon: '⬡', color: '#e4e4e7', role: 'System Designer',   description: 'Research-backed architecture with arxiv references.' },
}
export const P1_ORDER = [
  'explorer','skeptic','statistician','ethicist',
  'feature_engineer','pragmatist','devil_advocate','optimizer','architect',
]

// ── Node sizing (Increased for better legibility) ──────────────────────
const R   = 32  // Persona
const RP1 = 24  // Phase 1 agents
const RB  = 52  // Brief
const RS  = 52  // Synthesis

const GROUP_ORDER = ['theory', 'systems', 'applied', 'strategy']
const GROUP_TO_PERSONA: Record<string, string[]> = {
  theory:   ['andrej_karpathy', 'geoffrey_hinton', 'yann_lecun', 'francois_chollet', 'sebastian_raschka'],
  systems:  ['chip_huyen', 'edward_yang', 'matei_zaharia', 'vicki_boykis', 'tim_dettmers'],
  applied:  ['andrew_ng', 'jeremy_howard', 'santiago_valdarrama', 'jonas_mueller', 'jay_alammar'],
  strategy: ['sam_altman', 'ethan_mollick', 'chris_olah', 'lilian_weng', 'shreya_rajpal'],
}

const PERSONA_TO_GROUP: Record<string, string> = {}
Object.entries(GROUP_TO_PERSONA).forEach(([gk, ms]) => {
  ms.forEach(m => { PERSONA_TO_GROUP[m] = gk })
})

interface SimNode extends d3.SimulationNodeDatum {
  id: string; x?: number; y?: number; fx?: number | null; fy?: number | null
}
interface SimLink extends d3.SimulationLinkDatum<SimNode> { source: string | SimNode; target: string | SimNode }

interface Props {
  personas:         string[]
  activePersona?:   string
  donePersonas:     string[]
  champions:        string[]
  stage:            'groups' | 'champions' | 'synthesis' | 'phase1' | 'debate'
  synthesisDone:    boolean
  onSelectPersona?: (name: string) => void
  onSelectSynthesis?: () => void
  selectedPersona?: string
  phase1Agents:     string[]
  activeAgent?:     string
  activeGroup?:     string
}

export default function RedModeGraph({
  personas, activePersona, donePersonas, champions, stage, synthesisDone,
  onSelectPersona, onSelectSynthesis, selectedPersona, phase1Agents, activeAgent, activeGroup
}: Props) {
  const svgRef      = useRef<SVGSVGElement>(null)
  const nodeEls     = useRef<Map<string, SVGGElement>>(new Map())
  const p1ArcEls    = useRef<SVGPathElement[]>([])
  const r1Els       = useRef<SVGPathElement[]>([])
  const r2Els       = useRef<SVGPathElement[]>([])
  const r3Els       = useRef<SVGPathElement[]>([])
  
  const selected = selectedPersona ?? null
  const [selectedP1, setSelectedP1] = useState<string | null>(null)
  
  const stateRef = useRef({ synthesisDone, selected, onSelectSynthesis, onSelectPersona })
  stateRef.current = { synthesisDone, selected, onSelectSynthesis, onSelectPersona }

  useEffect(() => {
    if (!personas.length) return

    const svgEl = svgRef.current!
    const svg   = d3.select(svgEl)
    let sim: ReturnType<typeof d3.forceSimulation<SimNode>>
    let rafId: number
    let timeoutId: NodeJS.Timeout

    const build = () => {
      const W = svgEl.clientWidth  || 900
      const H = svgEl.clientHeight || 600

      svg.selectAll('*').remove()
      nodeEls.current.clear()
      p1ArcEls.current = []
      r1Els.current    = []
      r2Els.current    = []
      r3Els.current    = []

      // ── Defs ──────────────────────────────────────────────────
      const defs = svg.append('defs')

      const addGlow = (id: string, blur: number, count = 2) => {
        const f = defs.append('filter').attr('id', id)
          .attr('x','-50%').attr('y','-50%').attr('width','200%').attr('height','200%')
        f.append('feGaussianBlur').attr('in','SourceGraphic').attr('stdDeviation', blur).attr('result','blur')
        const m = f.append('feMerge')
        for (let i = 0; i < count; i++) m.append('feMergeNode').attr('in','blur')
        m.append('feMergeNode').attr('in','SourceGraphic')
      }
      addGlow('rm-glow', 10, 3)
      addGlow('rm-glow-done', 5, 1)

      const addArrow = (id: string, refX: number, color: string) =>
        defs.append('marker').attr('id', id)
          .attr('viewBox','0 -5 10 10').attr('refX', refX).attr('refY', 0)
          .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient','auto')
          .append('path').attr('d','M0,-5L10,0L0,5').attr('fill', color).attr('opacity', 0.65)

      addArrow('rm-arr-r1', R + 14, '#dc2626')
      addArrow('rm-arr-r3', RS + 14, '#f59e0b')

      // ── Nodes ─────────────────────────────────────────────────
      const briefNode: SimNode = { id: '__brief__',     fx: W * 0.12, fy: H / 2 }
      const synthNode: SimNode = { id: '__synthesis__', fx: W * 0.92, fy: H / 2 }

      // Spread out cluster centers to use more screen depth
      const clusterCenters: Record<string, { x: number, y: number }> = {
        theory:   { x: W * 0.40, y: H * 0.30 },
        systems:  { x: W * 0.70, y: H * 0.30 },
        applied:  { x: W * 0.40, y: H * 0.70 },
        strategy: { x: W * 0.70, y: H * 0.70 },
      }

      const simNodes: SimNode[] = [
        briefNode, synthNode,
        ...P1_ORDER.map(k => ({ id: `__p1_${k}__` } as SimNode)),
        ...personas.map(p => ({
          id: p,
          x: clusterCenters[PERSONA_TO_GROUP[p]]?.x ?? W/2,
          y: clusterCenters[PERSONA_TO_GROUP[p]]?.y ?? H/2
        } as SimNode)),
      ]

      const simLinks: SimLink[] = [
        ...P1_ORDER.map(k => ({ source: `__p1_${k}__`, target: '__brief__' })),
        ...personas.map(p  => ({ source: '__brief__',   target: p           })),
        ...personas.map(p  => ({ source: p,              target: '__synthesis__' })),
      ]

      // ── Simulation ────────────────────────────────────────────
      sim = d3.forceSimulation<SimNode>(simNodes)
        .alphaDecay(0.008)
        .velocityDecay(0.35)
        // Increased distance and repulsion to de-condense the graph
        .force('link',    d3.forceLink<SimNode, SimLink>(simLinks).id(d => d.id).distance(300).strength(0.06))
        .force('charge',  d3.forceManyBody().strength(-1200))
        .force('collide', d3.forceCollide((d: SimNode) =>
          d.id === '__brief__' || d.id === '__synthesis__' ? RB + 35 :
          d.id.startsWith('__p1_') ? RP1 + 25 : R + 25
        ).strength(1))
        .force('x', d3.forceX((d: any) => {
          const node = d as SimNode
          if (node.id === '__brief__') return W * 0.12
          if (node.id === '__synthesis__') return W * 0.92
          const gk = PERSONA_TO_GROUP[node.id]
          if (gk) return clusterCenters[gk].x
          return W * 0.55
        }).strength(0.15))
        .force('y', d3.forceY((d: any) => {
          const node = d as SimNode
          if (node.id === '__brief__' || node.id === '__synthesis__') return H / 2
          const gk = PERSONA_TO_GROUP[node.id]
          if (gk) return clusterCenters[gk].y
          return H / 2
        }).strength(0.15))

      const g = svg.append('g')
      const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.15, 3])
        .on('zoom', e => g.attr('transform', e.transform))
      svg.call(zoom).call(zoom.transform, d3.zoomIdentity.translate(W * 0.05, H * 0.05).scale(0.85))

      const linkGroup = g.append('g').attr('class', 'links')
      const nodeGroup = g.append('g').attr('class', 'nodes')

      // Arcs and Links
      const p1Arcs = linkGroup.selectAll<SVGPathElement, string>('path.p1arc')
        .data(P1_ORDER).join('path').attr('class','p1arc').attr('fill','none').attr('stroke-width', 1.2)
        .each(function() { p1ArcEls.current.push(this) })

      const r1Links = linkGroup.selectAll<SVGPathElement, SimLink>('path.r1')
        .data(personas.map(p => ({ source: '__brief__', target: p }))).join('path')
        .attr('class','r1').attr('fill','none').attr('stroke-width', 1.2).attr('marker-end', 'url(#rm-arr-r1)')
        .each(function() { r1Els.current.push(this) })

      const r3Links = linkGroup.selectAll<SVGPathElement, SimLink>('path.r3')
        .data(personas.map(p => ({ source: p, target: '__synthesis__' }))).join('path')
        .attr('class','r3').attr('fill','none').attr('stroke-width', 1.2).attr('marker-end', 'url(#rm-arr-r3)')
        .each(function() { r3Els.current.push(this) })

      // Nodes
      const nodeG = nodeGroup.selectAll<SVGGElement, SimNode>('g')
        .data(simNodes, d => d.id).join('g')
        .attr('cursor', 'pointer')
        .call(d3.drag<SVGGElement, SimNode>()
          .on('start', (ev, d) => {
            if (!ev.active) sim.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y })
          .on('end', (ev, d) => {
            if (!ev.active) sim.alphaTarget(0)
            if (!d.id.startsWith('__')) { d.fx = null; d.fy = null }
          }))
        .on('click', (ev, d) => {
          ev.stopPropagation()
          const st = stateRef.current
          if (d.id === '__synthesis__' && st.synthesisDone) {
            st.onSelectSynthesis?.()
            setSelectedP1(null)
          } else if (d.id.startsWith('__p1_') || d.id === '__brief__') {
            setSelectedP1(prev => d.id === prev ? null : d.id)
            st.onSelectPersona?.('')
          } else if (!d.id.startsWith('__')) {
            setSelectedP1(null)
            st.onSelectPersona?.(d.id === st.selected ? '' : d.id)
          }
        })

      nodeG.each(function(d) { nodeEls.current.set(d.id, this) })

      const getHex = (r: number) => [0, 1, 2, 3, 4, 5].map(i => `${Math.sin(i * Math.PI / 3) * r},${-Math.cos(i * Math.PI / 3) * r}`).join(' ')

      nodeG.append('polygon').attr('class','pulse-poly')
        .attr('points', d => getHex(d.id.startsWith('__p1_') ? RP1+12 : d.id.startsWith('__') ? RB+15 : R+12))
        .attr('fill','none').attr('stroke','none')

      nodeG.append('polygon').attr('class','main-poly')
        .attr('points', d => getHex(d.id.startsWith('__p1_') ? RP1 : d.id.startsWith('__') ? RB : R))
        .attr('fill','rgba(255,255,255,0.035)').attr('stroke','rgba(255,255,255,0.12)').attr('stroke-width', 2)

      nodeG.append('text').attr('class','icon-text')
        .attr('text-anchor','middle').attr('dominant-baseline','central')
        .attr('font-size', d => d.id.startsWith('__p1_') ? 14 : d.id.startsWith('__') ? 22 : 16)
        .attr('fill','rgba(255,255,255,0.35)').attr('pointer-events','none').attr('font-family', 'JetBrains Mono').attr('font-weight', '700')
        .text(d => {
          if (d.id === '__brief__') return '◈'
          if (d.id === '__synthesis__') return '◎'
          if (d.id.startsWith('__p1_')) return P1_META[d.id.slice(5, -2)]?.icon ?? '?'
          return PERSONA_META[d.id]?.icon ?? '??'
        })

      nodeG.append('text').attr('class','label-text')
        .attr('text-anchor','middle').attr('pointer-events','none')
        .attr('dy', d => d.id.startsWith('__p1_') ? RP1 + 20 : d.id.startsWith('__') ? RB + 24 : R + 22)
        .attr('font-size', 12).attr('fill','rgba(255,255,255,0.22)').attr('font-family', 'JetBrains Mono').attr('font-weight', '600')
        .text(d => {
          if (d.id === '__brief__') return 'Analysis Brief'
          if (d.id === '__synthesis__') return 'Synthesis'
          if (d.id.startsWith('__p1_')) return P1_META[d.id.slice(5, -2)]?.label
          return d.id.split('_').at(-1)!.replace(/^./, c => c.toUpperCase())
        })

      // Tick logic
      const arc = (sx: number, sy: number, tx: number, ty: number) => {
        const dr = Math.hypot(tx - sx, ty - sy) * 1.5
        return `M${sx},${sy} A${dr},${dr} 0 0,1 ${tx},${ty}`
      }

      sim.on('tick', () => {
        const currW = svgRef.current?.clientWidth || W
        const currH = svgRef.current?.clientHeight || H
        simNodes.forEach(d => {
          const r = d.id.startsWith('__p1_') ? RP1 + 10 : d.id.startsWith('__') ? RB + 10 : R + 10
          d.x = Math.max(r, Math.min(currW - r, d.x ?? currW / 2))
          d.y = Math.max(r, Math.min(currH - r, d.y ?? currH / 2))
        })
        p1ArcEls.current.forEach((el, i) => {
          const src = simNodes.find(n => n.id === `__p1_${P1_ORDER[i]}__`)
          const tgt = briefNode
          if (src && tgt) d3.select(el).attr('d', arc(src.x!, src.y!, tgt.x!, tgt.y!))
        })
        r1Els.current.forEach((el, i) => {
          const src = briefNode
          const tgt = simNodes.find(n => n.id === personas[i])
          if (src && tgt) d3.select(el).attr('d', arc(src.x!, src.y!, tgt.x!, tgt.y!))
        })
        r3Els.current.forEach((el, i) => {
          const src = simNodes.find(n => n.id === personas[i])
          const tgt = synthNode
          if (src && tgt) d3.select(el).attr('d', arc(src.x!, src.y!, tgt.x!, tgt.y!))
        })
        nodeG.attr('transform', d => `translate(${d.x},${d.y})`)
      })
    }

    timeoutId = setTimeout(() => { rafId = requestAnimationFrame(build) }, 500)
    return () => { clearTimeout(timeoutId); cancelAnimationFrame(rafId); sim?.stop() }
  }, [personas])

  // ── Update Visuals ──────────────────────────────────────────────────
  useEffect(() => {
    nodeEls.current.forEach((el, id) => {
      const sel = d3.select(el)
      const color = PERSONA_COLORS[id] ?? '#e11d48'
      const isActive = id === activePersona
      const isChamp  = champions.includes(id)
      const isDone   = donePersonas.includes(id)
      
      if (id.startsWith('__p1_')) {
        const k = id.slice(5, -2), isP1Done = phase1Agents.includes(k), isP1Act = activeAgent === k
        const c = P1_META[k]?.color ?? '#fff'
        sel.select('.main-poly').attr('fill', isP1Act ? `${c}40` : isP1Done ? `${c}12` : 'transparent').attr('stroke', isP1Act || isP1Done ? c : 'rgba(255,255,255,0.08)').attr('filter', isP1Act ? 'url(#rm-glow)' : null)
        sel.select('.icon-text').attr('fill', isP1Act || isP1Done ? c : 'rgba(255,255,255,0.22)').text(isP1Done ? '✓' : P1_META[k]?.icon)
      } else if (!id.startsWith('__')) {
        const gk = PERSONA_TO_GROUP[id]
        const isGroupAct = activeGroup === gk && stage === 'groups'
        const inDebate   = stage !== 'phase1'

        sel.select('.main-poly')
          .attr('fill', isActive ? `${color}45` : isChamp ? `${color}30` : isDone ? `${color}15` : 'transparent')
          .attr('stroke', (isActive || isChamp || (isGroupAct && inDebate)) ? color : 'rgba(255,255,255,0.1)')
          .attr('stroke-width', isActive ? 3 : isChamp ? 2 : 1.5)
          .attr('filter', isActive || (isChamp && stage === 'champions') ? 'url(#rm-glow)' : isChamp || isDone ? 'url(#rm-glow-done)' : null)
        
        sel.select('.pulse-poly')
          .attr('stroke', isActive ? color : 'none').attr('stroke-width', isActive ? 3 : 0).attr('opacity', isActive ? 0.5 : 0)

        sel.select('.icon-text').attr('fill', (isActive || isChamp || isDone) ? color : 'rgba(255,255,255,0.25)')
        sel.select('.label-text').attr('fill', (isActive || isChamp || isDone) ? color : 'rgba(255,255,255,0.18)').attr('font-weight', isActive || isChamp ? '700' : '600')
      }
    })

    // Link updates (increased visibility)
    r1Els.current.forEach((el, i) => {
      const name = personas[i], color = PERSONA_COLORS[name] ?? '#fff'
      const active = activePersona === name && stage === 'groups'
      const done   = donePersonas.includes(name)
      d3.select(el).attr('stroke', active ? color : done ? `${color}45` : 'rgba(220,38,38,0.08)').attr('stroke-width', active ? 2.5 : 1)
    })

    r3Els.current.forEach((el, i) => {
      const name = personas[i], color = PERSONA_COLORS[name] ?? '#fff'
      const active = (activePersona === name || champions.includes(name)) && stage === 'synthesis'
      d3.select(el).attr('stroke', active || synthesisDone ? color : 'transparent').attr('stroke-opacity', synthesisDone ? 0.75 : 0.35)
    })

  }, [activePersona, champions, donePersonas, stage, synthesisDone, phase1Agents, activeAgent, activeGroup, personas])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <svg ref={svgRef} width="100%" height="100%" style={{ background: 'transparent' }} />
      {selectedP1 && (
        <div style={{ position: 'absolute', top: 20, left: 20, padding: 16, background: 'rgba(5,1,1,0.9)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, maxWidth: 300, boxShadow: '0 12px 40px rgba(0,0,0,0.6)' }}>
           <h4 style={{ margin: '0 0 8px', color: '#fff', fontSize: 16 }}>{selectedP1.startsWith('__p1') ? P1_META[selectedP1.slice(5,-2)]?.label : 'Analysis Payload'}</h4>
           <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', lineHeight: 1.6, margin: 0 }}>{selectedP1.startsWith('__p1') ? P1_META[selectedP1.slice(5,-2)]?.description : 'Handover knowledge for the experts.'}</p>
        </div>
      )}
    </div>
  )
}
