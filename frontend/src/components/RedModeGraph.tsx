'use client'

import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

// ── Persona palette ───────────────────────────────────────────────────
export const PERSONA_COLORS: Record<string, string> = {
  andrej_karpathy: '#e11d48',
  yann_lecun: '#be123c',
  sam_altman: '#f43f5e',
  geoffrey_hinton: '#9f1239',
  francois_chollet: '#e11d48',
  andrew_ng: '#be123c',
  chip_huyen: '#f43f5e',
  jeremy_howard: '#fb7185',
  chris_olah: '#e11d48',
  edward_yang: '#be123c',
  ethan_mollick: '#f43f5e',
  jay_alammar: '#fb7185',
  jonas_mueller: '#e11d48',
  lilian_weng: '#be123c',
  matei_zaharia: '#9f1239',
  santiago_valdarrama: '#e11d48',
  sebastian_raschka: '#be123c',
  shreya_rajpal: '#f43f5e',
  tim_dettmers: '#fb7185',
  vicki_boykis: '#e11d48',
}

const PERSONA_META: Record<string, { icon: string; role: string }> = {
  andrej_karpathy: { icon: 'AK', role: 'Ex-Tesla AI Director' },
  yann_lecun: { icon: 'YL', role: 'Meta Chief AI Scientist' },
  sam_altman: { icon: 'SA', role: 'CEO, OpenAI' },
  geoffrey_hinton: { icon: 'GH', role: 'Godfather of Deep Learning' },
  francois_chollet: { icon: 'FC', role: 'Creator of Keras' },
  andrew_ng: { icon: 'AN', role: 'Founder, DeepLearning.AI' },
  chip_huyen: { icon: 'CH', role: 'ML Systems Engineer' },
  jeremy_howard: { icon: 'JH', role: 'Founder, fast.ai' },
  chris_olah: { icon: 'CO', role: 'Interpretability Researcher' },
  edward_yang: { icon: 'EY', role: 'PyTorch Core Developer' },
  ethan_mollick: { icon: 'EM', role: 'Wharton AI Professor' },
  jay_alammar: { icon: 'JA', role: 'ML Visualisation Expert' },
  jonas_mueller: { icon: 'JM', role: 'AutoML & Data Quality' },
  lilian_weng: { icon: 'LW', role: 'OpenAI Research Lead' },
  matei_zaharia: { icon: 'MZ', role: 'Co-creator of Apache Spark' },
  santiago_valdarrama: { icon: 'SV', role: 'ML Engineer & Educator' },
  sebastian_raschka: { icon: 'SR', role: 'ML Researcher & Author' },
  shreya_rajpal: { icon: 'SR', role: 'AI Reliability Engineer' },
  tim_dettmers: { icon: 'TD', role: 'Quantization Researcher' },
  vicki_boykis: { icon: 'VB', role: 'ML Engineer & Writer' },
}

export const P1_META: Record<string, { label: string; icon: string; color: string; role: string; description: string }> = {
  explorer: { label: 'Explorer', icon: '◉', color: '#a1a1aa', role: 'Data Scout', description: 'Scans structure, finds patterns and key features.' },
  skeptic: { label: 'Skeptic', icon: '⚠', color: '#71717a', role: 'Quality Guard', description: 'Challenges assumptions, flags anomalies and leakage.' },
  statistician: { label: 'Statistician', icon: '∑', color: '#d4d4d8', role: 'Numbers Expert', description: 'Distributions, correlations, hypothesis testing.' },
  ethicist: { label: 'Ethicist', icon: '⚖', color: '#a1a1aa', role: 'Bias Detector', description: 'Evaluates fairness and ethical implications.' },
  feature_engineer: { label: 'Feature Eng.', icon: '⟁', color: '#e4e4e7', role: 'Signal Extractor', description: 'New features, encodings, and transformations.' },
  pragmatist: { label: 'Pragmatist', icon: '◈', color: '#d4d4d8', role: 'Reality Check', description: 'Model plan — which models, eval metric, split.' },
  devil_advocate: { label: "Devil's Adv.", icon: '⛧', color: '#71717a', role: 'Critical Thinker', description: 'Stress-tests the plan, proposes alternatives.' },
  optimizer: { label: 'Optimizer', icon: '⚡', color: '#a1a1aa', role: 'Efficiency Expert', description: 'Hyperparameter tuning, CV strategy, ensembles.' },
  architect: { label: 'Architect', icon: '⬡', color: '#e4e4e7', role: 'System Designer', description: 'Research-backed architecture with arxiv references.' },
  constraint_discovery: { label: 'Constraints', icon: '⧖', color: '#a1a1aa', role: 'Structure Detector', description: 'Finds compositional rules: A = B + C, algebraic dependencies.' },
}
export const P1_ORDER = [
  'explorer', 'skeptic', 'statistician', 'ethicist',
  'feature_engineer', 'pragmatist', 'devil_advocate', 'optimizer', 'architect',
  'constraint_discovery',
]

// ── Node sizing (Increased for better legibility) ──────────────────────
const R = 32  // Persona
const RP1 = 24  // Phase 1 agents
const RB = 52  // Brief
const RS = 52  // Synthesis


const GROUP_TO_PERSONA: Record<string, string[]> = {
  theory: ['andrej_karpathy', 'geoffrey_hinton', 'yann_lecun', 'francois_chollet', 'sebastian_raschka'],
  systems: ['chip_huyen', 'edward_yang', 'matei_zaharia', 'vicki_boykis', 'tim_dettmers'],
  applied: ['andrew_ng', 'jeremy_howard', 'santiago_valdarrama', 'jonas_mueller', 'jay_alammar'],
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
  personas: string[]
  activePersonas?: string[]
  donePersonas: string[]
  champions: string[]
  stage: 'groups' | 'election' | 'champions' | 'synthesis' | 'phase1' | 'debate'
  synthesisDone: boolean
  onSelectPersona?: (name: string) => void
  onSelectSynthesis?: () => void
  selectedPersona?: string
  phase1Agents: string[]
  activeAgent?: string
  activeGroup?: string
}

export default function RedModeGraph({
  personas, activePersonas = [], donePersonas, champions, stage, synthesisDone,
  onSelectPersona, onSelectSynthesis, selectedPersona, phase1Agents, activeAgent, activeGroup
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const nodeEls = useRef<Map<string, SVGGElement>>(new Map())
  const p1ArcEls = useRef<SVGPathElement[]>([])
  const r1Els = useRef<SVGPathElement[]>([])
  const r2Els = useRef<SVGPathElement[]>([])
  const r3Els = useRef<SVGPathElement[]>([])
  const groupElsRef = useRef<{ el: SVGPathElement; src: string; tgt: string }[]>([])
  const champLinkGroupRef = useRef<SVGGElement | null>(null)
  const champEdgesRef = useRef<{ el: SVGPathElement; src: string; tgt: string }[]>([])
  // store simNodes so tick updates can access them from outside build
  const simNodesRef = useRef<SimNode[]>([])

  const selected = selectedPersona ?? null
  const [selectedP1, setSelectedP1] = useState<string | null>(null)

  const stateRef = useRef({ synthesisDone, selected, onSelectSynthesis, onSelectPersona })
  stateRef.current = { synthesisDone, selected, onSelectSynthesis, onSelectPersona }

  useEffect(() => {
    if (!personas.length) return

    const svgEl = svgRef.current!
    const svg = d3.select(svgEl)
    let sim: ReturnType<typeof d3.forceSimulation<SimNode>>
    let rafId: number
    let timeoutId: NodeJS.Timeout

    const build = () => {
      const W = svgEl.clientWidth || 900
      const H = svgEl.clientHeight || 600

      svg.selectAll('*').remove()
      nodeEls.current.clear()
      p1ArcEls.current = []
      r1Els.current = []
      r2Els.current = []
      r3Els.current = []
      groupElsRef.current = []
      champEdgesRef.current = []
      champLinkGroupRef.current = null

      // ── Defs ──────────────────────────────────────────────────
      const defs = svg.append('defs')

      const addGlow = (id: string, blur: number, count = 2) => {
        const f = defs.append('filter').attr('id', id)
          .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%')
        f.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', blur).attr('result', 'blur')
        const m = f.append('feMerge')
        for (let i = 0; i < count; i++) m.append('feMergeNode').attr('in', 'blur')
        m.append('feMergeNode').attr('in', 'SourceGraphic')
      }
      addGlow('rm-glow', 10, 3)
      addGlow('rm-glow-done', 5, 1)

      const addArrow = (id: string, refX: number, color: string) =>
        defs.append('marker').attr('id', id)
          .attr('viewBox', '0 -5 10 10').attr('refX', refX).attr('refY', 0)
          .attr('markerWidth', 7).attr('markerHeight', 7).attr('orient', 'auto')
          .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', color).attr('opacity', 0.65)

      addArrow('rm-arr-r1', R + 14, '#dc2626')
      addArrow('rm-arr-r3', RS + 14, '#f59e0b')

      // ── Nodes ─────────────────────────────────────────────────
      const briefNode: SimNode = { id: '__brief__', fx: W * 0.12, fy: H / 2 }
      const synthNode: SimNode = { id: '__synthesis__', fx: W * 0.92, fy: H / 2 }

      // Spread out cluster centers to use more screen depth
      const clusterCenters: Record<string, { x: number, y: number }> = {
        theory: { x: W * 0.40, y: H * 0.30 },
        systems: { x: W * 0.70, y: H * 0.30 },
        applied: { x: W * 0.40, y: H * 0.70 },
        strategy: { x: W * 0.70, y: H * 0.70 },
      }

      const simNodes: SimNode[] = [
        briefNode, synthNode,
        ...P1_ORDER.map(k => ({ id: `__p1_${k}__` } as SimNode)),
        ...personas.map(p => ({
          id: p,
          x: clusterCenters[PERSONA_TO_GROUP[p]]?.x ?? W / 2,
          y: clusterCenters[PERSONA_TO_GROUP[p]]?.y ?? H / 2
        } as SimNode)),
      ]

      // Intra-group pairs (for cluster cohesion)
      const intraPairs: { src: string; tgt: string }[] = []
      Object.values(GROUP_TO_PERSONA).forEach(members => {
        for (let i = 0; i < members.length; i++)
          for (let j = i + 1; j < members.length; j++)
            intraPairs.push({ src: members[i], tgt: members[j] })
      })

      const simLinks: SimLink[] = [
        ...P1_ORDER.map(k => ({ source: `__p1_${k}__`, target: '__brief__' })),
        ...personas.map(p => ({ source: '__brief__', target: p })),
        ...personas.map(p => ({ source: p, target: '__synthesis__' })),
        ...intraPairs.map(({ src, tgt }) => ({ source: src, target: tgt })),
      ]

      // ── Simulation ────────────────────────────────────────────
      sim = d3.forceSimulation<SimNode>(simNodes)
        .alphaDecay(0.008)
        .velocityDecay(0.35)
        // Increased distance and repulsion to de-condense the graph
        .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id(d => d.id).distance((l: SimLink) => {
          const sid = typeof l.source === 'string' ? l.source : (l.source as SimNode).id
          const tid = typeof l.target === 'string' ? l.target : (l.target as SimNode).id
          // intra-group: short distance to cluster; brief/synth: longer
          const sameGroup = PERSONA_TO_GROUP[sid] && PERSONA_TO_GROUP[sid] === PERSONA_TO_GROUP[tid]
          return sameGroup ? 120 : 300
        }).strength((l: SimLink) => {
          const sid = typeof l.source === 'string' ? l.source : (l.source as SimNode).id
          const tid = typeof l.target === 'string' ? l.target : (l.target as SimNode).id
          const sameGroup = PERSONA_TO_GROUP[sid] && PERSONA_TO_GROUP[sid] === PERSONA_TO_GROUP[tid]
          return sameGroup ? 0.12 : 0.06
        }))
        .force('charge', d3.forceManyBody().strength(-1200))
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
      linkGroup.selectAll<SVGPathElement, string>('path.p1arc')
        .data(P1_ORDER).join('path').attr('class', 'p1arc').attr('fill', 'none').attr('stroke-width', 1.2)
        .each(function () { p1ArcEls.current.push(this) })

      linkGroup.selectAll<SVGPathElement, SimLink>('path.r1')
        .data(personas.map(p => ({ source: '__brief__', target: p }))).join('path')
        .attr('class', 'r1').attr('fill', 'none').attr('stroke-width', 1.2).attr('marker-end', 'url(#rm-arr-r1)')
        .each(function () { r1Els.current.push(this) })

      linkGroup.selectAll<SVGPathElement, SimLink>('path.r3')
        .data(personas.map(p => ({ source: p, target: '__synthesis__' }))).join('path')
        .attr('class', 'r3').attr('fill', 'none').attr('stroke-width', 1.2).attr('marker-end', 'url(#rm-arr-r3)')
        .each(function () { r3Els.current.push(this) })

      // Intra-group edges (hidden by default, lit during Stage A)
      intraPairs.forEach(({ src, tgt }) => {
        const el = linkGroup.append('path').attr('class', 'grp-link')
          .attr('fill', 'none').attr('stroke', 'transparent').attr('stroke-width', 1)
          .node()!
        groupElsRef.current.push({ el, src, tgt })
      })

      // Champion cross-debate edges (dynamic — rebuilt in visual update)
      const champLinkG = linkGroup.append('g').attr('class', 'champ-links')
      champLinkGroupRef.current = champLinkG.node()

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

      nodeG.each(function (d) { nodeEls.current.set(d.id, this) })

      const getHex = (r: number) => [0, 1, 2, 3, 4, 5].map(i => `${Math.sin(i * Math.PI / 3) * r},${-Math.cos(i * Math.PI / 3) * r}`).join(' ')

      nodeG.append('polygon').attr('class', 'main-poly')
        .attr('points', d => getHex(d.id.startsWith('__p1_') ? RP1 : d.id.startsWith('__') ? RB : R))
        .attr('fill', 'rgba(255,255,255,0.035)').attr('stroke', 'rgba(255,255,255,0.12)').attr('stroke-width', 2)

      nodeG.append('text').attr('class', 'icon-text')
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
        .attr('font-size', d => d.id.startsWith('__p1_') ? 14 : d.id.startsWith('__') ? 22 : 16)
        .attr('fill', 'rgba(255,255,255,0.35)').attr('pointer-events', 'none').attr('font-family', 'JetBrains Mono').attr('font-weight', '700')
        .text(d => {
          if (d.id === '__brief__') return '◈'
          if (d.id === '__synthesis__') return '◎'
          if (d.id.startsWith('__p1_')) return P1_META[d.id.slice(5, -2)]?.icon ?? '?'
          return PERSONA_META[d.id]?.icon ?? '??'
        })

      nodeG.append('text').attr('class', 'label-text')
        .attr('text-anchor', 'middle').attr('pointer-events', 'none')
        .attr('dy', d => d.id.startsWith('__p1_') ? RP1 + 20 : d.id.startsWith('__') ? RB + 24 : R + 22)
        .attr('font-size', 12).attr('fill', 'rgba(255,255,255,0.22)').attr('font-family', 'JetBrains Mono').attr('font-weight', '600')
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

      simNodesRef.current = simNodes

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
        // Intra-group edges
        groupElsRef.current.forEach(({ el, src, tgt }) => {
          const s = simNodes.find(n => n.id === src)
          const t = simNodes.find(n => n.id === tgt)
          if (s && t) d3.select(el).attr('d', arc(s.x!, s.y!, t.x!, t.y!))
        })
        // Champion cross-debate edges
        champEdgesRef.current.forEach(({ el, src, tgt }) => {
          const s = simNodes.find(n => n.id === src)
          const t = simNodes.find(n => n.id === tgt)
          if (s && t) d3.select(el).attr('d', arc(s.x!, s.y!, t.x!, t.y!))
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
      const isChamp = champions.includes(id)
      const isDone = donePersonas.includes(id)

      if (id.startsWith('__p1_')) {
        const k = id.slice(5, -2), isP1Done = phase1Agents.includes(k), isP1Act = activeAgent === k
        const c = P1_META[k]?.color ?? '#fff'

        // Main hexagon update
        sel.select('.main-poly')
          .attr('fill', isP1Act ? `${c}55` : isP1Done ? `${c}12` : 'transparent')
          .attr('stroke', isP1Act ? '#fff' : isP1Done ? c : 'rgba(255,255,255,0.08)') // White stroke for current active
          .attr('stroke-width', isP1Act ? 5 : isP1Done ? 2 : 1.5)
          .attr('filter', isP1Act ? 'url(#rm-glow)' : isP1Done ? 'url(#rm-glow-done)' : null)

        // Icon update
        sel.select('.icon-text')
          .attr('fill', isP1Act || isP1Done ? c : 'rgba(255,255,255,0.22)')
          .attr('font-weight', isP1Act ? '800' : '700')
          .text(isP1Done ? '✓' : P1_META[k]?.icon)
      } else if (!id.startsWith('__')) {
        const gk = PERSONA_TO_GROUP[id]
        const isGroupAct = activeGroup === gk && (stage === 'groups' || stage === 'election')
        const inDebate = stage !== 'phase1'
        const isElecting = stage === 'election' && isChamp
        const isActive = activePersonas.includes(id)

        sel.select('.main-poly')
          .attr('fill', isActive ? `${color}55` : isElecting ? `${color}40` : isChamp ? `${color}35` : isDone ? `${color}28` : 'transparent')
          .attr('stroke', (isActive || isElecting || isChamp || isDone || (isGroupAct && inDebate)) ? color : 'rgba(255,255,255,0.1)')
          .attr('stroke-width', isActive ? 3 : isElecting ? 2.5 : isChamp ? 2 : isDone ? 1.5 : 1)
          .attr('filter', isActive || isElecting || (isChamp && stage === 'champions') ? 'url(#rm-glow)' : isChamp || isDone ? 'url(#rm-glow-done)' : null)

        sel.select('.icon-text').attr('fill', (isActive || isElecting || isChamp || isDone) ? color : 'rgba(255,255,255,0.25)')
          .text(isElecting ? '★' : isDone && !isActive ? '✓' : (PERSONA_META[id]?.icon ?? id.slice(0, 2).toUpperCase()))
        sel.select('.label-text').attr('fill', (isActive || isElecting || isChamp || isDone) ? color : 'rgba(255,255,255,0.18)').attr('font-weight', isActive || isChamp ? '700' : '600')
      }
    })

    // ── P1 arc strokes (visible as "done" once Phase 2 starts) ──
    const p1AllDone = stage !== 'phase1'
    p1ArcEls.current.forEach((el, i) => {
      const k = P1_ORDER[i]
      const isDoneP1 = phase1Agents.includes(k)
      const isActP1 = activeAgent === k
      const c = P1_META[k]?.color ?? '#aaa'
      d3.select(el)
        .attr('stroke', isActP1 ? c : isDoneP1 || p1AllDone ? `${c}55` : 'transparent')
        .attr('stroke-width', isActP1 ? 2 : 1)
    })

    // ── Brief → persona links ────────────────────────────────────
    r1Els.current.forEach((el, i) => {
      const name = personas[i], color = PERSONA_COLORS[name] ?? '#fff'
      const active = activePersonas.includes(name) && (stage === 'groups' || stage === 'election')
      const done = donePersonas.includes(name)
      d3.select(el).attr('stroke', active ? color : done ? `${color}45` : 'rgba(220,38,38,0.08)').attr('stroke-width', active ? 2.5 : 1)
    })

    // ── Persona → synthesis links ────────────────────────────────
    r3Els.current.forEach((el, i) => {
      const name = personas[i], color = PERSONA_COLORS[name] ?? '#fff'
      const active = (activePersonas.includes(name) || champions.includes(name)) && stage === 'synthesis'
      d3.select(el).attr('stroke', active || synthesisDone ? color : 'transparent').attr('stroke-opacity', synthesisDone ? 0.75 : 0.35)
    })

    // ── Intra-group edges (Stage A / election) ───────────────────
    groupElsRef.current.forEach(({ el, src, tgt }) => {
      const gk = PERSONA_TO_GROUP[src]
      const groupAct = activeGroup === gk
      const inStageA = stage === 'groups' || stage === 'election'
      const bothDone = donePersonas.includes(src) && donePersonas.includes(tgt)
      const eitherAct = activePersonas.includes(src) || activePersonas.includes(tgt)
      const color = PERSONA_COLORS[src] ?? '#e11d48'
      d3.select(el)
        .attr('stroke',
          eitherAct && inStageA ? `${color}80`
            : bothDone && inStageA ? `${color}30`
              : groupAct && inStageA ? `${color}25`
                : 'transparent'
        )
        .attr('stroke-width', eitherAct ? 1.5 : 1)
        .attr('stroke-dasharray', eitherAct ? 'none' : '4,4')
    })

    // ── Champion cross-debate edges (Stage B) ────────────────────
    if (champLinkGroupRef.current) {
      const champG = d3.select(champLinkGroupRef.current)
      champG.selectAll('*').remove()
      champEdgesRef.current = []

      if (stage === 'champions' && champions.length >= 2) {
        for (let i = 0; i < champions.length; i++) {
          for (let j = i + 1; j < champions.length; j++) {
            const src = champions[i], tgt = champions[j]
            const bothAct = activePersonas.includes(src) && activePersonas.includes(tgt)
            const el = champG.append('path')
              .attr('fill', 'none')
              .attr('stroke', bothAct ? '#f59e0b' : 'rgba(245,158,11,0.35)')
              .attr('stroke-width', bothAct ? 2 : 1.2)
              .attr('stroke-dasharray', bothAct ? 'none' : '6,4')
              .attr('marker-end', 'url(#rm-arr-r3)')
              .node()!
            champEdgesRef.current.push({ el, src, tgt })
          }
        }
        // Immediately draw paths with current node positions
        champEdgesRef.current.forEach(({ el, src, tgt }) => {
          const s = simNodesRef.current.find(n => n.id === src)
          const t = simNodesRef.current.find(n => n.id === tgt)
          if (s?.x && t?.x) {
            const dr = Math.hypot(t.x - s.x, t.y! - s.y!) * 1.5
            d3.select(el).attr('d', `M${s.x},${s.y} A${dr},${dr} 0 0,1 ${t.x},${t.y}`)
          }
        })
      }
    }

  }, [activePersonas, champions, donePersonas, stage, synthesisDone, phase1Agents, activeAgent, activeGroup, personas])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <svg ref={svgRef} width="100%" height="100%" style={{ background: 'transparent' }} />
      {selectedP1 && (
        <div style={{ position: 'absolute', top: 20, left: 20, padding: 16, background: 'rgba(5,1,1,0.9)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, maxWidth: 300, boxShadow: '0 12px 40px rgba(0,0,0,0.6)' }}>
          <h4 style={{ margin: '0 0 8px', color: '#fff', fontSize: 16 }}>{selectedP1.startsWith('__p1') ? P1_META[selectedP1.slice(5, -2)]?.label : 'Analysis Payload'}</h4>
          <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)', lineHeight: 1.6, margin: 0 }}>{selectedP1.startsWith('__p1') ? P1_META[selectedP1.slice(5, -2)]?.description : 'Handover knowledge for the experts.'}</p>
        </div>
      )}
    </div>
  )
}
