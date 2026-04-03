'use client'

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

interface AgentNode {
  id: string
  label: string
  icon: string
  color: string
  role: string
  description: string
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface AgentLink {
  source: string | AgentNode
  target: string | AgentNode
  label: string
}

const NODES: AgentNode[] = [
  { id: 'explorer',         label: 'Explorer',        icon: '◉', color: '#7c6fcd', role: 'Data Scout',        description: 'Scans structure, finds patterns and key features.' },
  { id: 'skeptic',          label: 'Skeptic',          icon: '⚠', color: '#d46b8a', role: 'Quality Guard',     description: 'Challenges assumptions, flags anomalies and leakage.' },
  { id: 'statistician',     label: 'Statistician',     icon: '∑', color: '#4a9fd4', role: 'Numbers Expert',    description: 'Distributions, correlations, hypothesis testing.' },
  { id: 'ethicist',         label: 'Ethicist',         icon: '⚖', color: '#d4874a', role: 'Bias Detector',     description: 'Evaluates fairness and ethical implications.' },
  { id: 'feature_engineer', label: 'Feature Eng.',     icon: '⟁', color: '#3db87a', role: 'Signal Extractor',  description: 'New features, encodings, and transformations.' },
  { id: 'pragmatist',       label: 'Pragmatist',       icon: '◈', color: '#c4a832', role: 'Reality Check',     description: 'Model plan — which models, eval metric, split.' },
  { id: 'devil_advocate',   label: 'Devil Adv.',       icon: '⛧', color: '#e63030', role: 'Critical Thinker',  description: 'Stress-tests the plan, proposes alternatives.' },
  { id: 'optimizer',        label: 'Optimizer',        icon: '⚡', color: '#8a7cd4', role: 'Efficiency Expert', description: 'Hyperparameter tuning, CV strategy, ensembles.' },
  { id: 'architect',        label: 'Architect',        icon: '⬡', color: '#a86cd4', role: 'System Designer',   description: 'Deployment architecture and serving infra.' },
  { id: 'storyteller',      label: 'Storyteller',      icon: '✦', color: '#d4a8c4', role: 'Insight Narrator',  description: 'Synthesises findings into the final narrative.' },
]

// Directed edges showing information flow through the pipeline
const LINKS: AgentLink[] = [
  { source: 'explorer',         target: 'feature_engineer', label: 'EDA →' },
  { source: 'explorer',         target: 'pragmatist',        label: 'context' },
  { source: 'skeptic',          target: 'pragmatist',        label: 'quality' },
  { source: 'statistician',     target: 'pragmatist',        label: 'stats' },
  { source: 'statistician',     target: 'optimizer',         label: 'metrics' },
  { source: 'ethicist',         target: 'pragmatist',        label: 'ethics' },
  { source: 'feature_engineer', target: 'pragmatist',        label: 'features' },
  { source: 'pragmatist',       target: 'devil_advocate',    label: 'plan' },
  { source: 'pragmatist',       target: 'optimizer',         label: 'plan' },
  { source: 'pragmatist',       target: 'architect',         label: 'design' },
  { source: 'devil_advocate',   target: 'architect',         label: 'critique' },
  { source: 'optimizer',        target: 'architect',         label: 'tuning' },
  { source: 'architect',        target: 'storyteller',       label: 'system' },
]

interface Props {
  activeAgent: string
  doneAgents: string[]
  done: boolean
}

export default function AgentGraph({ activeAgent, doneAgents, done }: Props) {
  const svgRef  = useRef<SVGSVGElement>(null)
  const gRef    = useRef<SVGGElement | null>(null)
  const simRef  = useRef<d3.Simulation<AgentNode, AgentLink> | null>(null)
  const [selected, setSelected] = useState<AgentNode | null>(null)

  useLayoutEffect(() => {
    const svg = d3.select(svgRef.current!)
    svg.selectAll('*').remove()

    const W = svgRef.current!.clientWidth  || window.innerWidth  || 800
    const H = svgRef.current!.clientHeight || (window.innerHeight - 76) || 600

    // ── Defs: arrow markers per agent color + glow filter ──────────────
    const defs = svg.append('defs')

    NODES.forEach(n => {
      defs.append('marker')
        .attr('id', `arrow-${n.id}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', n.color)
        .attr('opacity', 0.5)
    })

    // Glow filter for active node
    const filter = defs.append('filter').attr('id', 'glow')
    filter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'coloredBlur')
    const feMerge = filter.append('feMerge')
    feMerge.append('feMergeNode').attr('in', 'coloredBlur')
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic')

    // ── Main group (zoom target) ────────────────────────────────────────
    const g = svg.append('g')
    gRef.current = g.node()

    // ── Zoom + pan ──────────────────────────────────────────────────────
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', e => g.attr('transform', e.transform))

    svg.call(zoom)
      .call(zoom.transform, d3.zoomIdentity.translate(W * 0.05, H * 0.05).scale(0.9))

    // ── Force simulation ────────────────────────────────────────────────
    const nodes: AgentNode[] = NODES.map(n => ({ ...n }))
    const links: AgentLink[] = LINKS.map(l => ({ ...l }))

    const sim = d3.forceSimulation<AgentNode>(nodes)
      .force('link', d3.forceLink<AgentNode, AgentLink>(links)
        .id(d => d.id)
        .distance(160)
        .strength(0.4)
      )
      .force('charge', d3.forceManyBody().strength(-500))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collide', d3.forceCollide(55))
      .force('x', d3.forceX(W / 2).strength(0.03))
      .force('y', d3.forceY(H / 2).strength(0.03))

    simRef.current = sim

    // ── Edge lines ──────────────────────────────────────────────────────
    const linkGroup = g.append('g').attr('class', 'links')

    const linkLines = linkGroup.selectAll<SVGPathElement, AgentLink>('path')
      .data(links)
      .join('path')
      .attr('fill', 'none')
      .attr('stroke', 'rgba(255,255,255,0.08)')
      .attr('stroke-width', 1.5)

    // ── Edge labels ─────────────────────────────────────────────────────
    const linkLabels = linkGroup.selectAll<SVGTextElement, AgentLink>('text')
      .data(links)
      .join('text')
      .attr('fill', 'rgba(255,255,255,0.18)')
      .attr('font-size', 8)
      .attr('font-family', "'JetBrains Mono', monospace")
      .attr('text-anchor', 'middle')
      .attr('dy', -4)
      .text(d => d.label)

    // ── Node groups ─────────────────────────────────────────────────────
    const nodeGroup = g.append('g').attr('class', 'nodes')

    const nodeG = nodeGroup.selectAll<SVGGElement, AgentNode>('g')
      .data(nodes, d => d.id)
      .join('g')
      .attr('cursor', 'pointer')
      .call(
        d3.drag<SVGGElement, AgentNode>()
          .on('start', (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) sim.alphaTarget(0)
            d.fx = null; d.fy = null
          })
      )
      .on('click', (event, d) => {
        event.stopPropagation()
        setSelected(prev => prev?.id === d.id ? null : NODES.find(n => n.id === d.id) || null)
      })

    // Outer glow ring (for active state)
    nodeG.append('circle')
      .attr('class', 'glow-ring')
      .attr('r', 22)
      .attr('fill', 'none')
      .attr('stroke-width', 0)

    // Main circle
    nodeG.append('circle')
      .attr('class', 'main-circle')
      .attr('r', 18)
      .attr('stroke-width', 2)

    // Icon text
    nodeG.append('text')
      .attr('class', 'icon-text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('dy', -1)
      .attr('font-size', 14)
      .text(d => d.icon)

    // Label below
    nodeG.append('text')
      .attr('class', 'label-text')
      .attr('text-anchor', 'middle')
      .attr('dy', 34)
      .attr('font-size', 10)
      .attr('font-family', "'JetBrains Mono', monospace")
      .text(d => d.label)

    // ── Dismiss detail on svg click ─────────────────────────────────────
    svg.on('click', () => setSelected(null))

    // ── Tick ────────────────────────────────────────────────────────────
    sim.on('tick', () => {
      linkLines.attr('d', (d: AgentLink) => {
        const s = d.source as AgentNode
        const t = d.target as AgentNode
        const dx = (t.x ?? 0) - (s.x ?? 0)
        const dy = (t.y ?? 0) - (s.y ?? 0)
        const dr = Math.sqrt(dx * dx + dy * dy) * 1.4
        return `M${s.x},${s.y} A${dr},${dr} 0 0,1 ${t.x},${t.y}`
      })

      linkLabels.attr('x', (d: AgentLink) => {
        const s = d.source as AgentNode; const t = d.target as AgentNode
        return ((s.x ?? 0) + (t.x ?? 0)) / 2
      }).attr('y', (d: AgentLink) => {
        const s = d.source as AgentNode; const t = d.target as AgentNode
        return ((s.y ?? 0) + (t.y ?? 0)) / 2
      })

      nodeG.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    // Set arrow markers on links
    linkLines.attr('marker-end', (d: AgentLink) => {
      const t = typeof d.target === 'string' ? d.target : (d.target as AgentNode).id
      return `url(#arrow-${t})`
    })

    return () => { sim.stop() }
  }, [])

  // ── Update node visuals when active/done state changes ─────────────
  useEffect(() => {
    if (!gRef.current) return
    const g = d3.select(gRef.current)

    g.selectAll<SVGGElement, AgentNode>('.nodes g').each(function(d) {
      const el       = d3.select(this)
      const isActive = activeAgent === d.id
      const isDone   = doneAgents.includes(d.id)
      const node     = NODES.find(n => n.id === d.id)!

      el.select('.main-circle')
        .attr('fill', isDone
          ? 'rgba(52,211,153,0.15)'
          : isActive
            ? `${node.color}22`
            : 'rgba(255,255,255,0.03)')
        .attr('stroke', isDone
          ? '#34d399'
          : isActive
            ? node.color
            : 'rgba(255,255,255,0.12)')
        .attr('stroke-width', isActive ? 2.5 : isDone ? 2 : 1.5)
        .attr('filter', isActive ? 'url(#glow)' : null)

      el.select('.icon-text')
        .attr('fill', isDone ? '#34d399' : isActive ? node.color : 'rgba(255,255,255,0.4)')
        .attr('font-size', isDone ? 12 : 14)
        .text(isDone ? '✓' : node.icon)

      el.select('.label-text')
        .attr('fill', isDone
          ? 'rgba(52,211,153,0.7)'
          : isActive
            ? node.color
            : 'rgba(255,255,255,0.25)')

      // Glow ring for active node
      el.select('.glow-ring')
        .attr('stroke', isActive ? node.color : 'none')
        .attr('stroke-width', isActive ? 1.5 : 0)
        .attr('opacity', isActive ? 0.35 : 0)

      // Edges — highlight edges from/to active node
      if (gRef.current) {
        d3.select(gRef.current).selectAll<SVGPathElement, AgentLink>('.links path')
          .attr('stroke', (link: AgentLink) => {
            const s = typeof link.source === 'string' ? link.source : (link.source as AgentNode).id
            const t = typeof link.target === 'string' ? link.target : (link.target as AgentNode).id
            if (activeAgent && (s === activeAgent || t === activeAgent)) {
              const activeNode = NODES.find(n => n.id === activeAgent)
              return activeNode ? `${activeNode.color}60` : 'rgba(255,255,255,0.2)'
            }
            return 'rgba(255,255,255,0.06)'
          })
          .attr('stroke-width', (link: AgentLink) => {
            const s = typeof link.source === 'string' ? link.source : (link.source as AgentNode).id
            const t = typeof link.target === 'string' ? link.target : (link.target as AgentNode).id
            return (activeAgent && (s === activeAgent || t === activeAgent)) ? 2 : 1.2
          })
      }
    })
  }, [activeAgent, doneAgents, done])

  const selectedMeta = selected ? NODES.find(n => n.id === selected.id) : null

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'transparent' }}>
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        style={{ display: 'block' }}
      />

      {/* Detail panel — top right, like MiroFish */}
      {selectedMeta && (
        <div style={{
          position: 'absolute', top: 16, right: 16,
          width: 240,
          background: 'rgba(6,2,2,0.82)',
          backdropFilter: 'blur(24px)',
          border: `1px solid ${selectedMeta.color}35`,
          borderRadius: 14,
          overflow: 'hidden',
          boxShadow: `0 16px 48px rgba(0,0,0,0.5), 0 0 0 1px ${selectedMeta.color}10`,
        }}>
          {/* Top accent bar */}
          <div style={{ height: 2, background: `linear-gradient(90deg, ${selectedMeta.color}, transparent)` }} />
          <div style={{ padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: `${selectedMeta.color}15`,
                border: `1px solid ${selectedMeta.color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16, color: selectedMeta.color,
              }}>
                {doneAgents.includes(selectedMeta.id) ? '✓' : selectedMeta.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: selectedMeta.color, fontFamily: "'Space Grotesk',sans-serif" }}>{selectedMeta.label}</div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.28)', marginTop: 1 }}>{selectedMeta.role}</div>
              </div>
              <button
                onClick={() => setSelected(null)}
                style={{ width: 22, height: 22, borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >✕</button>
            </div>
            <div style={{ height: 1, background: `${selectedMeta.color}15`, marginBottom: 10 }} />
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', lineHeight: 1.65, margin: 0 }}>
              {selectedMeta.description}
            </p>
            <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
              <span style={{
                fontSize: 9.5, padding: '3px 8px', borderRadius: 5,
                background: doneAgents.includes(selectedMeta.id)
                  ? 'rgba(52,211,153,0.1)' : activeAgent === selectedMeta.id
                    ? `${selectedMeta.color}15` : 'rgba(255,255,255,0.04)',
                border: `1px solid ${doneAgents.includes(selectedMeta.id)
                  ? 'rgba(52,211,153,0.25)' : activeAgent === selectedMeta.id
                    ? `${selectedMeta.color}30` : 'rgba(255,255,255,0.08)'}`,
                color: doneAgents.includes(selectedMeta.id)
                  ? '#34d399' : activeAgent === selectedMeta.id
                    ? selectedMeta.color : 'rgba(255,255,255,0.25)',
                fontFamily: "'JetBrains Mono',monospace",
              }}>
                {doneAgents.includes(selectedMeta.id) ? 'DONE' : activeAgent === selectedMeta.id ? 'ACTIVE' : 'PENDING'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{ position: 'absolute', bottom: 16, left: 16, display: 'flex', gap: 16, alignItems: 'center' }}>
        {[
          { color: 'rgba(255,255,255,0.15)', label: 'Pending' },
          { color: '#e63030',                label: 'Active' },
          { color: '#34d399',                label: 'Done' },
        ].map(l => (
          <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: l.color }} />
            <span style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.25)', fontFamily: "'JetBrains Mono',monospace" }}>{l.label}</span>
          </div>
        ))}
        <span style={{ fontSize: 9.5, color: 'rgba(255,255,255,0.15)', fontFamily: "'JetBrains Mono',monospace", marginLeft: 4 }}>
          drag · scroll to zoom · click node
        </span>
      </div>
    </div>
  )
}
