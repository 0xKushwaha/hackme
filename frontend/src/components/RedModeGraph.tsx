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

const R   = 24
const RP1 = 18
const RB  = 34
const RS  = 34

interface SimNode {
  id: string; x?: number; y?: number; fx?: number | null; fy?: number | null
}
interface SimLink { source: string | SimNode; target: string | SimNode }
interface R2Pair  { a: string; b: string }

interface Props {
  personas:         string[]
  activePersona?:   string
  doneR1:           string[]
  doneR2:           string[]
  currentRound:     number
  synthesisDone:    boolean
  onSelectPersona?: (name: string) => void
  onSelectSynthesis?: () => void
  selectedPersona?: string
  phase:            'phase1' | 'debate'
  phase1Agents:     string[]
  activeAgent?:     string
}

export default function RedModeGraph({
  personas, activePersona, doneR1, doneR2, currentRound, synthesisDone,
  onSelectPersona, onSelectSynthesis, selectedPersona, phase, phase1Agents, activeAgent,
}: Props) {
  const svgRef      = useRef<SVGSVGElement>(null)
  const nodeEls     = useRef<Map<string, SVGGElement>>(new Map())
  const p1ArcEls    = useRef<SVGPathElement[]>([])
  const r1Els       = useRef<SVGPathElement[]>([])
  const r2Els       = useRef<SVGPathElement[]>([])
  const r3Els       = useRef<SVGPathElement[]>([])
  const r2PairsRef  = useRef<R2Pair[]>([])
  const personasRef = useRef<string[]>([])
  const selected    = selectedPersona ?? null
  const [selectedP1, setSelectedP1] = useState<string | null>(null)
  
  // Track state for the D3 closure
  const stateRef = useRef({ synthesisDone, selected, onSelectSynthesis, onSelectPersona })
  stateRef.current = { synthesisDone, selected, onSelectSynthesis, onSelectPersona }

  // ── Build scene once (deferred one rAF for real SVG dimensions) ───
  useEffect(() => {
    if (!personas.length) return
    personasRef.current = personas

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
      addGlow('rm-glow', 8, 2)
      addGlow('rm-glow-done', 4, 1)

      const addArrow = (id: string, refX: number, color: string) =>
        defs.append('marker').attr('id', id)
          .attr('viewBox','0 -5 10 10').attr('refX', refX).attr('refY', 0)
          .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient','auto')
          .append('path').attr('d','M0,-5L10,0L0,5').attr('fill', color).attr('opacity', 0.65)

      addArrow('rm-arr-r1', R  + 10, '#dc2626')
      addArrow('rm-arr-r3', RS + 10, '#f59e0b')

      // ── Nodes ─────────────────────────────────────────────────
      const briefNode: SimNode = { id: '__brief__',     fx: W * 0.22, fy: H / 2 }
      const synthNode: SimNode = { id: '__synthesis__', fx: W * 0.85, fy: H / 2 }

      const pad = 60
      const allFloating = [
        ...P1_ORDER.map(k => ({ id: `__p1_${k}__` })),
        ...personas.map(p => ({ id: p })),
      ].map(n => ({
        ...n,
        x: pad + Math.random() * (W - pad * 2),
        y: pad + Math.random() * (H - pad * 2),
      })) as SimNode[]

      const p1Floating = allFloating.filter(n => n.id.startsWith('__p1_'))
      const pFloating  = allFloating.filter(n => !n.id.startsWith('__p1_'))
      const simNodes   = [...allFloating, briefNode, synthNode]

      // R2 full mesh
      const pairs: R2Pair[] = []
      for (let i = 0; i < personas.length; i++)
        for (let j = i + 1; j < personas.length; j++)
          pairs.push({ a: personas[i], b: personas[j] })
      r2PairsRef.current = pairs

      // ── Link topology (mirrors visible arcs) ──────────────────
      const simLinks: SimLink[] = [
        ...P1_ORDER.map(k => ({ source: `__p1_${k}__`, target: '__brief__' })),
        ...personas.map(p  => ({ source: '__brief__',   target: p           })),
        ...personas.map(p  => ({ source: p,              target: '__synthesis__' })),
      ]

      // ── Simulation ────────────────────────────────────────────
      sim = d3.forceSimulation<SimNode>(simNodes)
        .alphaDecay(0.012)
        .velocityDecay(0.45)
        .force('link',    d3.forceLink<SimNode, SimLink>(simLinks).id(d => d.id).distance(260).strength(0.08))
        .force('charge',  d3.forceManyBody().strength(-700))
        .force('collide', d3.forceCollide((d: SimNode) =>
          d.id === '__brief__' || d.id === '__synthesis__' ? RB + 18 :
          d.id.startsWith('__p1_') ? RP1 + 14 : R + 14
        ).strength(0.8))
        .force('cx', d3.forceX(W * 0.52).strength(0.03))
        .force('cy', d3.forceY(H * 0.50).strength(0.03))

      // ── Groups ────────────────────────────────────────────────
      const g    = svg.append('g')
      const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.15, 3])
        .on('zoom', e => g.attr('transform', e.transform))
      svg.call(zoom).call(zoom.transform, d3.zoomIdentity.translate(W * 0.09, H * 0.04).scale(0.93))

      const r2Group   = g.append('g')
      const arcGroup  = g.append('g')
      const nodeGroup = g.append('g')

      // ── P1 → Brief arcs ───────────────────────────────────────
      arcGroup.selectAll<SVGPathElement, string>('path.p1arc')
        .data(P1_ORDER).join('path')
        .attr('class','p1arc').attr('fill','none')
        .attr('stroke','rgba(255,255,255,0.04)').attr('stroke-width', 0.6)
        .each(function() { p1ArcEls.current.push(this) })

      // ── Brief → Persona arcs (R1) ─────────────────────────────
      arcGroup.selectAll<SVGPathElement, SimLink>('path.r1')
        .data(personas.map(p => ({ source: '__brief__', target: p }))).join('path')
        .attr('class','r1').attr('fill','none')
        .attr('stroke','rgba(220,38,38,0.04)').attr('stroke-width', 0.6)
        .attr('marker-end','url(#rm-arr-r1)')
        .each(function() { r1Els.current.push(this) })

      // ── Persona → Synthesis arcs (R3) ─────────────────────────
      arcGroup.selectAll<SVGPathElement, SimLink>('path.r3')
        .data(personas.map(p => ({ source: p, target: '__synthesis__' }))).join('path')
        .attr('class','r3').attr('fill','none')
        .attr('stroke','rgba(245,158,11,0)').attr('stroke-width', 0.6)
        .attr('marker-end','url(#rm-arr-r3)')
        .each(function() { r3Els.current.push(this) })

      // ── R2 full mesh ──────────────────────────────────────────
      r2Group.selectAll<SVGPathElement, R2Pair>('path')
        .data(pairs).join('path')
        .attr('fill','none').attr('stroke','rgba(220,38,38,0.02)').attr('stroke-width', 0.35)
        .each(function() { r2Els.current.push(this) })

      // ── Node groups ───────────────────────────────────────────
      const nodeG = nodeGroup.selectAll<SVGGElement, SimNode>('g')
        .data(simNodes, d => d.id).join('g')
        .attr('cursor', d => d.id === '__synthesis__' && synthesisDone ? 'pointer' : d.id.startsWith('__') ? 'default' : 'grab')
        .call(
          d3.drag<SVGGElement, SimNode>()
            .on('start', (ev, d) => {
              ev.sourceEvent?.stopPropagation()
              if (!ev.active) sim.alphaTarget(0.5).restart()
              d.fx = d.x ?? 0; d.fy = d.y ?? 0
            })
            .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y })
            .on('end',  (ev, d) => {
              if (!ev.active) sim.alphaTarget(0)
              if (!d.id.startsWith('__')) { d.fx = null; d.fy = null }
            })
        )
        .on('click', (ev, d) => {
          ev.stopPropagation()
          const st = stateRef.current
          if (d.id === '__synthesis__' && st.synthesisDone) {
            st.onSelectSynthesis?.()
            setSelectedP1(null)
            return
          }
          if (d.id.startsWith('__p1_') || d.id === '__brief__') {
            setSelectedP1(prev => d.id === prev ? null : d.id)
            st.onSelectPersona?.('') // Close debate panels if open
            return
          }
          if (d.id === '__synthesis__') return
          
          setSelectedP1(null)
          st.onSelectPersona?.(d.id === st.selected ? '' : d.id)
        })

      nodeG.each(function(d) { nodeEls.current.set(d.id, this) })

      const getHex = (r: number) => [0, 1, 2, 3, 4, 5].map(i => `${Math.sin(i * Math.PI / 3) * r},${-Math.cos(i * Math.PI / 3) * r}`).join(' ')

      nodeG.append('polygon').attr('class','pulse-poly')
        .attr('points', d => {
          const r = d.id === '__brief__' || d.id === '__synthesis__' ? RB + 10 :
                    d.id.startsWith('__p1_') ? RP1 + 8 : R + 10;
          return getHex(r);
        })
        .attr('fill','none').attr('stroke','none').attr('stroke-width', 0)

      nodeG.append('polygon').attr('class','main-poly')
        .attr('points', d => {
          const r = d.id === '__brief__' || d.id === '__synthesis__' ? RB :
                    d.id.startsWith('__p1_') ? RP1 : R;
          return getHex(r);
        })
        .attr('fill','rgba(255,255,255,0.02)')
        .attr('stroke','rgba(255,255,255,0.08)')
        .attr('stroke-width', 1.5)

      nodeG.append('text').attr('class','icon-text')
        .attr('text-anchor','middle').attr('dominant-baseline','central')
        .attr('font-size', d =>
          d.id === '__brief__' || d.id === '__synthesis__' ? 15 :
          d.id.startsWith('__p1_') ? 10 : 11)
        .attr('font-weight','700')
        .attr('font-family',"'JetBrains Mono', monospace")
        .attr('fill','rgba(255,255,255,0.22)').attr('pointer-events','none')
        .text(d => {
          if (d.id === '__brief__')     return '◈'
          if (d.id === '__synthesis__') return '◎'
          if (d.id.startsWith('__p1_')) return P1_META[d.id.slice(5,-2)]?.icon ?? '?'
          return PERSONA_META[d.id]?.icon ?? '??'
        })

      nodeG.append('text').attr('class','label-text')
        .attr('text-anchor','middle').attr('pointer-events','none')
        .attr('dy', d =>
          d.id === '__brief__' || d.id === '__synthesis__' ? RB + 14 :
          d.id.startsWith('__p1_') ? RP1 + 13 : R + 14)
        .attr('font-size', d => d.id.startsWith('__p1_') ? 8.5 : 9.5)
        .attr('font-family',"'JetBrains Mono', monospace")
        .attr('fill','rgba(255,255,255,0.16)')
        .text(d => {
          if (d.id === '__brief__')     return 'Brief'
          if (d.id === '__synthesis__') return 'Synthesis'
          if (d.id.startsWith('__p1_')) return P1_META[d.id.slice(5,-2)]?.label ?? d.id.slice(5,-2)
          return d.id.split('_').at(-1)!.replace(/^./, c => c.toUpperCase())
        })

      svg.on('click', () => onSelectPersona?.(''))

      // ── Tick ──────────────────────────────────────────────────
      const nodeById = Object.fromEntries(simNodes.map(n => [n.id, n]))
      const arc = (sx: number, sy: number, tx: number, ty: number) => {
        const dr = Math.hypot(tx - sx, ty - sy) * 1.3
        return `M${sx},${sy} A${dr},${dr} 0 0,1 ${tx},${ty}`
      }

      sim.on('tick', () => {
        const bpP1 = RP1 + 8, bpP = R + 8
        p1Floating.forEach(d => {
          d.x = Math.max(bpP1, Math.min(W - bpP1, d.x ?? W / 2))
          d.y = Math.max(bpP1, Math.min(H - bpP1, d.y ?? H / 2))
        })
        pFloating.forEach(d => {
          d.x = Math.max(bpP, Math.min(W - bpP, d.x ?? W / 2))
          d.y = Math.max(bpP, Math.min(H - bpP, d.y ?? H / 2))
        })

        p1ArcEls.current.forEach((el, i) => {
          const src = nodeById[`__p1_${P1_ORDER[i]}__`]
          const tgt = nodeById['__brief__']
          if (src && tgt) d3.select(el).attr('d', arc(src.x!, src.y!, tgt.x!, tgt.y!))
        })

        r1Els.current.forEach((el, i) => {
          const src = nodeById['__brief__']
          const tgt = pFloating[i]
          if (src && tgt) d3.select(el).attr('d', arc(src.x!, src.y!, tgt.x!, tgt.y!))
        })

        r2Els.current.forEach((el, i) => {
          const pair = r2PairsRef.current[i]
          if (!pair) return
          const a = nodeById[pair.a], b = nodeById[pair.b]
          if (a && b) d3.select(el).attr('d', `M${a.x},${a.y} L${b.x},${b.y}`)
        })

        r3Els.current.forEach((el, i) => {
          const src = pFloating[i]
          const tgt = nodeById['__synthesis__']
          if (src && tgt) d3.select(el).attr('d', arc(src.x!, src.y!, tgt.x!, tgt.y!))
        })

        nodeG.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
      })
    }

    timeoutId = setTimeout(() => {
      rafId = requestAnimationFrame(build)
    }, 450)
    
    return () => { 
      clearTimeout(timeoutId)
      cancelAnimationFrame(rafId)
      sim?.stop() 
    }
  }, [personas]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Update visuals ─────────────────────────────────────────────────
  useEffect(() => {
    if (!personas.length) return

    nodeEls.current.forEach((el, id) => {
      const sel = d3.select(el)

      if (id === '__brief__') {
        const allDone = phase1Agents.length === P1_ORDER.length
        sel.select('.main-poly')
          .attr('fill',         allDone ? 'rgba(225,29,72,0.18)' : 'rgba(225,29,72,0.06)')
          .attr('stroke',       '#e11d48')
          .attr('stroke-width', allDone ? 2 : 1)
          .attr('filter',       allDone ? 'url(#rm-glow)' : 'url(#rm-glow-done)')
        sel.select('.icon-text').attr('fill', '#e11d48')
        sel.select('.label-text').attr('fill', '#e11d48').attr('font-weight','600')
        return
      }

      if (id === '__synthesis__') {
        sel.select('.main-poly')
          .attr('fill',         synthesisDone ? 'rgba(225,29,72,0.18)' : 'rgba(225,29,72,0.06)')
          .attr('stroke',       '#e11d48')
          .attr('stroke-width', synthesisDone ? 2 : 1)
          .attr('filter',       synthesisDone ? 'url(#rm-glow)' : 'url(#rm-glow-done)')
        sel.select('.icon-text').attr('fill', '#e11d48')
        sel.select('.label-text').attr('fill', '#e11d48').attr('font-weight','600')
        return
      }

      if (id.startsWith('__p1_')) {
        const k      = id.slice(5, -2)
        const color  = P1_META[k]?.color ?? '#a1a1aa'
        const isDone = phase1Agents.includes(k)
        const isAct  = activeAgent === k
        sel.select('.main-poly')
          .attr('fill',         isAct ? `${color}30` : isDone ? `${color}18` : 'rgba(255,255,255,0.02)')
          .attr('stroke',       isAct || isDone ? color : 'rgba(255,255,255,0.07)')
          .attr('stroke-width', isAct ? 2 : isDone ? 1.5 : 1)
          .attr('filter',       isAct ? 'url(#rm-glow)' : isDone ? 'url(#rm-glow-done)' : null)
        sel.select('.pulse-poly')
          .attr('stroke', isAct ? color : 'none').attr('stroke-width', isAct ? 1.5 : 0).attr('opacity', isAct ? 0.4 : 0)
        sel.select('.icon-text')
          .attr('fill', isAct || isDone ? color : 'rgba(255,255,255,0.18)')
          .text(isDone ? '✓' : P1_META[k]?.icon ?? '?')
        sel.select('.label-text')
          .attr('fill',        isDone ? color : isAct ? 'rgba(255,255,255,0.65)' : 'rgba(255,255,255,0.14)')
          .attr('font-weight', isDone ? '600' : '400')
        return
      }

      // Persona node
      const color    = PERSONA_COLORS[id] ?? '#e11d48'
      const isActive = id === activePersona
      const r1done   = doneR1.includes(id)
      const r2done   = doneR2.includes(id)
      const inDebate = phase === 'debate'

      sel.select('.main-poly')
        .attr('fill',         isActive ? `${color}35` : r1done ? `${color}18` : 'rgba(255,255,255,0.015)')
        .attr('stroke',       inDebate && (isActive || r1done) ? color : 'rgba(255,255,255,0.06)')
        .attr('stroke-width', isActive ? 2 : r1done ? 1.5 : 1)
        .attr('filter',       isActive ? 'url(#rm-glow)' : r1done ? 'url(#rm-glow-done)' : null)
      sel.select('.pulse-poly')
        .attr('stroke', isActive ? color : 'none').attr('stroke-width', isActive ? 2 : 0).attr('opacity', isActive ? 0.45 : 0)
      sel.select('.icon-text')
        .attr('fill', inDebate && (isActive || r1done) ? color : 'rgba(255,255,255,0.15)')
        .text(r2done ? '✓' : PERSONA_META[id]?.icon ?? '??')
      sel.select('.label-text')
        .attr('fill',        inDebate && (isActive || r2done) ? color : inDebate && r1done ? `${color}88` : 'rgba(255,255,255,0.1)')
        .attr('font-weight', inDebate && (isActive || r2done) ? '600' : '400')
    })

    // P1 → Brief arc styles
    p1ArcEls.current.forEach((el, i) => {
      const k      = P1_ORDER[i]
      const color  = P1_META[k]?.color ?? '#38bdf8'
      const isDone = phase1Agents.includes(k)
      const isAct  = activeAgent === k
      d3.select(el)
        .attr('stroke',         isAct || isDone ? color : 'rgba(255,255,255,0.04)')
        .attr('stroke-opacity', isAct ? 0.8 : isDone ? 0.45 : 1)
        .attr('stroke-width',   isAct ? 2.2 : isDone ? 1.4 : 0.5)
    })

    // R1 arc styles
    r1Els.current.forEach((el, i) => {
      const name   = personasRef.current[i]
      if (!name) return
      const color  = PERSONA_COLORS[name] ?? '#dc2626'
      const active = activePersona === name && currentRound === 1
      const r1done = doneR1.includes(name)
      d3.select(el)
        .attr('stroke',       active ? `${color}bb` : r1done ? `${color}40` : 'rgba(220,38,38,0.03)')
        .attr('stroke-width', active ? 2.2 : r1done ? 1.3 : 0.5)
    })

    // R2 mesh styles
    r2Els.current.forEach((el, i) => {
      const pair = r2PairsRef.current[i]
      if (!pair) return
      const aDone = doneR2.includes(pair.a), bDone = doneR2.includes(pair.b)
      const aAct  = activePersona === pair.a && currentRound === 2
      const bAct  = activePersona === pair.b && currentRound === 2
      const anyAct = aAct || bAct, bothDone = aDone && bDone
      const alpha  = anyAct ? 0.7 : bothDone ? 0.2 : (aDone || bDone) ? 0.06 : currentRound >= 2 ? 0.025 : 0.02
      d3.select(el)
        .attr('stroke',         anyAct ? (PERSONA_COLORS[pair.a] ?? '#dc2626') : bothDone ? (PERSONA_COLORS[pair.a] ?? '#dc2626') : '#dc2626')
        .attr('stroke-opacity', alpha)
        .attr('stroke-width',   anyAct ? 2.0 : bothDone ? 0.6 : 0.35)
    })

    // R3 arc styles
    r3Els.current.forEach((el, i) => {
      const name  = personasRef.current[i]
      if (!name) return
      const color = PERSONA_COLORS[name] ?? '#f59e0b'
      const alpha = synthesisDone ? 0.55 : (currentRound >= 3 ? 0.2 : 0)
      d3.select(el)
        .attr('stroke',         alpha > 0 ? color : 'transparent')
        .attr('stroke-opacity', alpha)
        .attr('stroke-width',   synthesisDone ? 1.5 : 0.8)
    })

  }, [activePersona, doneR1, doneR2, currentRound, synthesisDone, personas, selected, phase, phase1Agents, activeAgent])

  let tooltipNode = null
  if (selectedP1 === '__brief__') {
    tooltipNode = { key: 'brief', label: 'Analysis Brief', icon: '◈', color: '#e11d48', role: 'State Payload', description: 'The aggregate knowledge generated by the Phase 1 agents. This is passed directly into the context window for all debating personas.' }
  } else if (selectedP1?.startsWith('__p1_')) {
    const k = selectedP1.slice(5, -2)
    tooltipNode = { key: k, ...P1_META[k] }
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }} onClick={() => setSelectedP1(null)}>
      <svg ref={svgRef} width="100%" height="100%" style={{ display: 'block' }} />
      
      {/* Description card for Phase 1 and Context nodes */}
      {tooltipNode && (
        <div onClick={e => e.stopPropagation()} style={{
          position: 'absolute', top: 16, right: 16, width: 260, zIndex: 20,
          background: 'rgba(5,1,1,0.95)', backdropFilter: 'blur(24px)',
          border: `1px solid ${tooltipNode.color}40`, borderRadius: 14, overflow: 'hidden',
          boxShadow: `0 16px 48px rgba(0,0,0,0.8), 0 0 32px ${tooltipNode.color}15`,
        }}>
          <div style={{ height: 2, background: `linear-gradient(90deg, ${tooltipNode.color}, transparent)` }} />
          <div style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: `${tooltipNode.color}15`, border: `1px solid ${tooltipNode.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, color: tooltipNode.color }}>
                {tooltipNode.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: tooltipNode.color, fontFamily: "'Space Grotesk',sans-serif" }}>{tooltipNode.label}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', marginTop: 1 }}>{tooltipNode.role}</div>
              </div>
              <button onClick={e => { e.stopPropagation(); setSelectedP1(null) }} style={{ width: 22, height: 22, borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
            </div>
            <div style={{ height: 1, background: `${tooltipNode.color}15`, marginBottom: 10 }} />
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.38)', lineHeight: 1.65, margin: 0 }}>{tooltipNode.description}</p>
          </div>
        </div>
      )}

      <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', gap: 16, alignItems: 'center' }}>
        <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.1)', fontFamily: "'JetBrains Mono',monospace", marginLeft: 4 }}>
          drag · scroll · click
        </span>
      </div>
    </div>
  )
}
