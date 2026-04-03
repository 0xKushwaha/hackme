'use client'

import { useLayoutEffect, useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

export interface NodeData {
  key: string; label: string; icon: string; color: string; role: string
  description: string; content: string
}

export const PIPELINE_NODES: Omit<NodeData, 'content'>[] = [
  { key: 'explorer',         label: 'Explorer',        icon: '◉', color: '#7c6fcd', role: 'Data Scout',        description: 'Scans structure, finds patterns and key features.' },
  { key: 'skeptic',          label: 'Skeptic',          icon: '⚠', color: '#d46b8a', role: 'Quality Guard',     description: 'Challenges assumptions, flags anomalies and leakage.' },
  { key: 'statistician',     label: 'Statistician',     icon: '∑', color: '#4a9fd4', role: 'Numbers Expert',    description: 'Distributions, correlations, hypothesis testing.' },
  { key: 'ethicist',         label: 'Ethicist',         icon: '⚖', color: '#d4874a', role: 'Bias Detector',     description: 'Evaluates fairness and ethical implications.' },
  { key: 'feature_engineer', label: 'Feature Eng.',     icon: '⟁', color: '#3db87a', role: 'Signal Extractor',  description: 'New features, encodings, and transformations.' },
  { key: 'pragmatist',       label: 'Pragmatist',       icon: '◈', color: '#c4a832', role: 'Reality Check',     description: 'Model plan — which models, eval metric, split.' },
  { key: 'devil_advocate',   label: 'Devil Adv.',       icon: '⛧', color: '#e63030', role: 'Critical Thinker',  description: 'Stress-tests the plan, proposes alternatives.' },
  { key: 'optimizer',        label: 'Optimizer',        icon: '⚡', color: '#8a7cd4', role: 'Efficiency Expert', description: 'Hyperparameter tuning, CV strategy, ensembles.' },
  { key: 'architect',        label: 'Architect',        icon: '⬡', color: '#a86cd4', role: 'System Designer',   description: 'Research-backed architecture with arxiv references.' },
  { key: 'final_report',     label: 'Final Report',     icon: '◎', color: '#f0c040', role: 'Pipeline Output',   description: 'Complete analysis: findings, metrics, recommendations.' },
]

interface D3Node { id: string; x?: number; y?: number; fx?: number | null; fy?: number | null }
interface D3Link { source: string | D3Node; target: string | D3Node; label: string }

const LINKS: D3Link[] = [
  { source: 'explorer',         target: 'feature_engineer', label: 'EDA'     },
  { source: 'explorer',         target: 'pragmatist',        label: 'context' },
  { source: 'skeptic',          target: 'pragmatist',        label: 'quality' },
  { source: 'statistician',     target: 'pragmatist',        label: 'stats'   },
  { source: 'statistician',     target: 'optimizer',         label: 'metrics' },
  { source: 'ethicist',         target: 'pragmatist',        label: 'ethics'  },
  { source: 'feature_engineer', target: 'pragmatist',        label: 'features'},
  { source: 'pragmatist',       target: 'devil_advocate',    label: 'plan'    },
  { source: 'pragmatist',       target: 'optimizer',         label: 'plan'    },
  { source: 'pragmatist',       target: 'architect',         label: 'design'  },
  { source: 'devil_advocate',   target: 'architect',         label: 'critique'},
  { source: 'optimizer',        target: 'architect',         label: 'tuning'  },
  { source: 'architect',        target: 'final_report',      label: 'architecture' },
]

const R = 26
const R_FINAL = 34

interface Props {
  activeAgent: string
  doneAgents: string[]
  done: boolean
  nodes: NodeData[]
  selectedKey?: string | null
  onSelect?: (key: string | null) => void
}

export default function PipelineGraph({ activeAgent, doneAgents, done, nodes, selectedKey, onSelect }: Props) {
  const svgRef   = useRef<SVGSVGElement>(null)
  const nodeEls  = useRef<Map<string, SVGGElement>>(new Map())
  const linkEls  = useRef<SVGPathElement[]>([])
  const linkData = useRef<D3Link[]>([])
  // Internal state fallback when no external control provided
  const [internalSelected, setInternalSelected] = useState<string | null>(null)
  const selected    = selectedKey !== undefined ? selectedKey : internalSelected
  const setSelected = onSelect ?? setInternalSelected

  const nodeMap = Object.fromEntries(nodes.map(n => [n.key, n]))
  const staticMap = Object.fromEntries(PIPELINE_NODES.map(n => [n.key, n]))

  // ── Build scene once ────────────────────────────────────────────────────────
  useLayoutEffect(() => {
    const svgEl = svgRef.current!
    const svg   = d3.select(svgEl)
    svg.selectAll('*').remove()
    nodeEls.current.clear()
    linkEls.current = []

    const W = svgEl.clientWidth  || window.innerWidth  || 900
    const H = svgEl.clientHeight || window.innerHeight || 700

    const defs = svg.append('defs')

    PIPELINE_NODES.forEach(n => {
      const r = n.key === 'final_report' ? R_FINAL : R
      defs.append('marker')
        .attr('id', `pg-arrow-${n.key}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', r + 8).attr('refY', 0)
        .attr('markerWidth', 7).attr('markerHeight', 7)
        .attr('orient', 'auto')
        .append('path').attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', n.color).attr('opacity', 0.6)
    })

    const f = defs.append('filter').attr('id', 'pg-glow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%')
    f.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', '8').attr('result', 'blur')
    const fm = f.append('feMerge')
    fm.append('feMergeNode').attr('in', 'blur')
    fm.append('feMergeNode').attr('in', 'blur')
    fm.append('feMergeNode').attr('in', 'SourceGraphic')

    const fd = defs.append('filter').attr('id', 'pg-glow-done').attr('x', '-40%').attr('y', '-40%').attr('width', '180%').attr('height', '180%')
    fd.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', '4').attr('result', 'blur')
    const fmd = fd.append('feMerge')
    fmd.append('feMergeNode').attr('in', 'blur')
    fmd.append('feMergeNode').attr('in', 'SourceGraphic')

    const g = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 3])
      .on('zoom', e => g.attr('transform', e.transform))
    svg.call(zoom).call(zoom.transform, d3.zoomIdentity.translate(W * 0.08, H * 0.08).scale(0.85))

    const simNodes: D3Node[] = PIPELINE_NODES.map(n => ({ id: n.key }))
    const simLinks: D3Link[] = LINKS.map(l => ({ ...l }))
    linkData.current = simLinks

    const sim = d3.forceSimulation<D3Node>(simNodes)
      .force('link',    d3.forceLink<D3Node, D3Link>(simLinks).id(d => d.id).distance(180).strength(0.35))
      .force('charge',  d3.forceManyBody().strength(-700))
      .force('center',  d3.forceCenter(W / 2, H / 2))
      .force('collide', d3.forceCollide(70))
      .force('x',       d3.forceX(W / 2).strength(0.02))
      .force('y',       d3.forceY(H / 2).strength(0.02))

    const linkGroup = g.append('g')
    const linkPaths = linkGroup.selectAll<SVGPathElement, D3Link>('path')
      .data(simLinks).join('path')
      .attr('fill', 'none')
      .attr('stroke', 'rgba(255,255,255,0.07)')
      .attr('stroke-width', 1.2)
      .attr('marker-end', (d: D3Link) => {
        const t = typeof d.target === 'string' ? d.target : (d.target as D3Node).id
        return `url(#pg-arrow-${t})`
      })
    linkPaths.each(function() { linkEls.current.push(this) })

    const linkLabels = linkGroup.selectAll<SVGTextElement, D3Link>('text')
      .data(simLinks).join('text')
      .attr('fill', 'rgba(255,255,255,0.14)')
      .attr('font-size', 9)
      .attr('font-family', "'JetBrains Mono', monospace")
      .attr('text-anchor', 'middle')
      .attr('pointer-events', 'none')
      .text(d => d.label)

    const nodeGroup = g.append('g')
    const nodeG = nodeGroup.selectAll<SVGGElement, D3Node>('g')
      .data(simNodes, d => d.id)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, D3Node>()
          .on('start', (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
          .on('drag',  (ev, d) => { d.fx = ev.x; d.fy = ev.y })
          .on('end',   (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      )
      .on('click', (ev, d) => { ev.stopPropagation(); setSelected(selected === d.id ? null : d.id) })

    nodeG.each(function(d) { nodeEls.current.set(d.id, this) })

    nodeG.append('circle').attr('class', 'pulse-ring')
      .attr('r', d => (d.id === 'final_report' ? R_FINAL : R) + 10)
      .attr('fill', 'none').attr('stroke', 'none').attr('stroke-width', 0)

    nodeG.append('circle').attr('class', 'main-circle')
      .attr('r', d => d.id === 'final_report' ? R_FINAL : R)
      .attr('fill', 'rgba(255,255,255,0.03)')
      .attr('stroke', 'rgba(255,255,255,0.12)')
      .attr('stroke-width', 1.5)

    nodeG.append('text').attr('class', 'icon-text')
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
      .attr('font-size', d => d.id === 'final_report' ? 20 : 16)
      .attr('fill', 'rgba(255,255,255,0.35)').attr('pointer-events', 'none')
      .text(d => staticMap[d.id]?.icon ?? '◌')

    nodeG.append('text').attr('class', 'label-text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => (d.id === 'final_report' ? R_FINAL : R) + 16)
      .attr('font-size', 11)
      .attr('font-family', "'JetBrains Mono', monospace")
      .attr('fill', 'rgba(255,255,255,0.22)').attr('pointer-events', 'none')
      .text(d => staticMap[d.id]?.label ?? d.id)

    svg.on('click', () => setSelected(null))

    sim.on('tick', () => {
      linkPaths.attr('d', (d: D3Link) => {
        const s = d.source as D3Node, t = d.target as D3Node
        const dr = Math.sqrt(((t.x ?? 0) - (s.x ?? 0)) ** 2 + ((t.y ?? 0) - (s.y ?? 0)) ** 2) * 1.3
        return `M${s.x},${s.y} A${dr},${dr} 0 0,1 ${t.x},${t.y}`
      })
      linkLabels
        .attr('x', (d: D3Link) => (((d.source as D3Node).x ?? 0) + ((d.target as D3Node).x ?? 0)) / 2)
        .attr('y', (d: D3Link) => (((d.source as D3Node).y ?? 0) + ((d.target as D3Node).y ?? 0)) / 2)
      nodeG.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => { sim.stop() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Update visuals when state changes ───────────────────────────────────────
  useEffect(() => {
    nodeEls.current.forEach((el, id) => {
      const meta     = staticMap[id]!
      const isFinal  = id === 'final_report'
      const isActive = !isFinal && id === activeAgent
      const isDone   = isFinal ? done : doneAgents.includes(id)
      const sel      = d3.select(el)

      sel.select('.main-circle')
        .attr('fill',         isDone   ? `${meta.color}28` : isActive ? `${meta.color}30` : 'rgba(255,255,255,0.03)')
        .attr('stroke',       isDone || isActive ? meta.color : 'rgba(255,255,255,0.1)')
        .attr('stroke-width', isActive ? 3 : isDone ? 2.5 : 1.5)
        .attr('filter',       isActive ? 'url(#pg-glow)' : isDone ? 'url(#pg-glow-done)' : null)

      sel.select('.pulse-ring')
        .attr('stroke',       isActive ? meta.color : 'none')
        .attr('stroke-width', isActive ? 2 : 0)
        .attr('opacity',      isActive ? 0.4 : 0)

      sel.select('.icon-text')
        .attr('fill',      isDone || isActive ? meta.color : 'rgba(255,255,255,0.3)')
        .attr('font-size', isFinal ? 20 : isActive ? 18 : 16)
        .text(isDone ? '✓' : meta.icon)

      sel.select('.label-text')
        .attr('fill',        isDone || isActive ? meta.color : 'rgba(255,255,255,0.22)')
        .attr('font-weight', isActive || isDone ? '600' : '400')
    })

    linkEls.current.forEach((el, i) => {
      const link = linkData.current[i]
      if (!link) return
      const s = typeof link.source === 'string' ? link.source : (link.source as D3Node).id
      const t = typeof link.target === 'string' ? link.target : (link.target as D3Node).id
      const connected = activeAgent && (s === activeAgent || t === activeAgent)
      const srcDone   = doneAgents.includes(s)
      const srcMeta   = staticMap[s]
      d3.select(el)
        .attr('stroke',       connected ? `${staticMap[activeAgent]?.color ?? '#fff'}80` : srcDone ? `${srcMeta?.color ?? '#fff'}25` : 'rgba(255,255,255,0.06)')
        .attr('stroke-width', connected ? 2.2 : srcDone ? 1.5 : 1.0)
    })
  }, [activeAgent, doneAgents, done]) // eslint-disable-line react-hooks/exhaustive-deps

  const selMeta = selected ? staticMap[selected] : null
  // Only show description card when node has no content (during run)
  const hasContent = selected ? !!nodeMap[selected]?.content : false

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <svg ref={svgRef} width="100%" height="100%" style={{ display: 'block' }} />

      {/* Description card — shown during run when node has no content yet */}
      {selMeta && !hasContent && (
        <div onClick={e => e.stopPropagation()} style={{
          position: 'absolute', top: 16, right: 16, width: 250, zIndex: 20,
          background: 'rgba(4,1,1,0.92)', backdropFilter: 'blur(24px)',
          border: `1px solid ${selMeta.color}40`, borderRadius: 14, overflow: 'hidden',
          boxShadow: `0 16px 48px rgba(0,0,0,0.6), 0 0 32px ${selMeta.color}18`,
        }}>
          <div style={{ height: 2, background: `linear-gradient(90deg, ${selMeta.color}, transparent)` }} />
          <div style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: `${selMeta.color}18`, border: `1px solid ${selMeta.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, color: selMeta.color }}>
                {doneAgents.includes(selMeta.key) ? '✓' : selMeta.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: selMeta.color, fontFamily: "'Space Grotesk',sans-serif" }}>{selMeta.label}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', marginTop: 1 }}>{selMeta.role}</div>
              </div>
              <button onClick={e => { e.stopPropagation(); setSelected(null) }} style={{ width: 22, height: 22, borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
            </div>
            <div style={{ height: 1, background: `${selMeta.color}15`, marginBottom: 10 }} />
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.38)', lineHeight: 1.65, margin: 0 }}>{selMeta.description}</p>
            <div style={{ marginTop: 10 }}>
              <span style={{
                fontSize: 9.5, padding: '3px 8px', borderRadius: 5, fontFamily: "'JetBrains Mono',monospace",
                background: doneAgents.includes(selMeta.key) || activeAgent === selMeta.key ? `${selMeta.color}18` : 'rgba(255,255,255,0.04)',
                border: `1px solid ${doneAgents.includes(selMeta.key) || activeAgent === selMeta.key ? `${selMeta.color}35` : 'rgba(255,255,255,0.08)'}`,
                color: doneAgents.includes(selMeta.key) || activeAgent === selMeta.key ? selMeta.color : 'rgba(255,255,255,0.25)',
              }}>
                {doneAgents.includes(selMeta.key) ? 'DONE' : activeAgent === selMeta.key ? 'ACTIVE' : 'PENDING'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{ position: 'absolute', bottom: 20, left: 20, display: 'flex', gap: 18, alignItems: 'center' }}>
        {[
          { color: 'rgba(255,255,255,0.2)', label: 'Pending' },
          { color: '#7c6fcd',               label: 'Active'  },
          { color: '#34d399',               label: 'Done'    },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: l.color, boxShadow: l.label === 'Active' ? `0 0 8px ${l.color}` : 'none' }} />
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', fontFamily: "'JetBrains Mono',monospace" }}>{l.label}</span>
          </div>
        ))}
        <span style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.15)', fontFamily: "'JetBrains Mono',monospace", marginLeft: 8 }}>
          {done ? 'click node to view output' : 'drag · scroll to zoom · click node'}
        </span>
      </div>
    </div>
  )
}
