'use client'

import { useLayoutEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface NodeData { key: string; label: string; icon: string; color: string; role: string; content: string }

interface D3Node { id: string; x?: number; y?: number; fx?: number | null; fy?: number | null }
interface D3Link { source: string | D3Node; target: string | D3Node }

const GRAPH_NODES = [
  'explorer','skeptic','statistician','ethicist','feature_engineer',
  'pragmatist','devil_advocate','optimizer','architect','storyteller','final_report',
]
const GRAPH_LINKS: D3Link[] = [
  { source: 'explorer',         target: 'feature_engineer' },
  { source: 'explorer',         target: 'pragmatist' },
  { source: 'skeptic',          target: 'pragmatist' },
  { source: 'statistician',     target: 'pragmatist' },
  { source: 'statistician',     target: 'optimizer' },
  { source: 'ethicist',         target: 'pragmatist' },
  { source: 'feature_engineer', target: 'pragmatist' },
  { source: 'pragmatist',       target: 'devil_advocate' },
  { source: 'pragmatist',       target: 'optimizer' },
  { source: 'pragmatist',       target: 'architect' },
  { source: 'devil_advocate',   target: 'architect' },
  { source: 'optimizer',        target: 'architect' },
  { source: 'architect',        target: 'storyteller' },
  { source: 'storyteller',      target: 'final_report' },
]

const R = 24
const R_FINAL = 32

interface Props { nodes: NodeData[] }

export default function ResultsGraph({ nodes }: Props) {
  const svgRef   = useRef<SVGSVGElement>(null)
  const nodeEls  = useRef<Map<string, SVGGElement>>(new Map())
  const [selected, setSelected] = useState<NodeData | null>(null)

  const nodeMap = Object.fromEntries(nodes.map(n => [n.key, n]))

  useLayoutEffect(() => {
    const svgEl = svgRef.current!
    const svg   = d3.select(svgEl)
    svg.selectAll('*').remove()
    nodeEls.current.clear()

    const W = svgEl.clientWidth  || window.innerWidth  || 900
    const H = svgEl.clientHeight || window.innerHeight || 700

    // ── Defs ──────────────────────────────────────────────────────────────
    const defs = svg.append('defs')

    nodes.forEach(n => {
      const r = n.key === 'final_report' ? R_FINAL : R
      defs.append('marker')
        .attr('id', `rarrow-${n.key}`)
        .attr('viewBox', '0 -5 10 10').attr('refX', r + 8).attr('refY', 0)
        .attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
        .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', n.color).attr('opacity', 0.55)
    })

    // Glow filter
    const f = defs.append('filter').attr('id', 'rglow').attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%')
    f.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', '7').attr('result', 'blur')
    const fm = f.append('feMerge')
    fm.append('feMergeNode').attr('in', 'blur')
    fm.append('feMergeNode').attr('in', 'blur')
    fm.append('feMergeNode').attr('in', 'SourceGraphic')

    const g = svg.append('g')
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 3])
      .on('zoom', e => g.attr('transform', e.transform))
    svg.call(zoom).call(zoom.transform, d3.zoomIdentity.translate(W * 0.08, H * 0.08).scale(0.85))

    // ── Simulation ────────────────────────────────────────────────────────
    const simNodes: D3Node[] = GRAPH_NODES.map(id => ({ id }))
    const simLinks: D3Link[] = GRAPH_LINKS.map(l => ({ ...l }))

    const sim = d3.forceSimulation<D3Node>(simNodes)
      .force('link',    d3.forceLink<D3Node, D3Link>(simLinks).id(d => d.id).distance(170).strength(0.35))
      .force('charge',  d3.forceManyBody().strength(-650))
      .force('center',  d3.forceCenter(W / 2, H / 2))
      .force('collide', d3.forceCollide(65))
      .force('x',       d3.forceX(W / 2).strength(0.02))
      .force('y',       d3.forceY(H / 2).strength(0.02))

    // ── Links ─────────────────────────────────────────────────────────────
    const linkGroup = g.append('g')
    const linkPaths = linkGroup.selectAll<SVGPathElement, D3Link>('path')
      .data(simLinks).join('path')
      .attr('fill', 'none')
      .attr('stroke-width', 1.2)
      .attr('marker-end', (d: D3Link) => {
        const t = typeof d.target === 'string' ? d.target : (d.target as D3Node).id
        const nd = nodeMap[t]
        return nd ? `url(#rarrow-${t})` : null
      })
      .attr('stroke', (d: D3Link) => {
        const s = typeof d.source === 'string' ? d.source : (d.source as D3Node).id
        const nd = nodeMap[s]
        return nd ? `${nd.color}30` : 'rgba(255,255,255,0.06)'
      })

    // ── Nodes ─────────────────────────────────────────────────────────────
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
      .on('click', (ev, d) => {
        ev.stopPropagation()
        const nd = nodeMap[d.id]
        if (nd) setSelected(p => p?.key === d.id ? null : nd)
      })

    nodeG.each(function(d) { nodeEls.current.set(d.id, this) })

    nodeG.each(function(d) {
      const nd  = nodeMap[d.id]
      const isFinal = d.id === 'final_report'
      const r   = isFinal ? R_FINAL : R
      const sel = d3.select(this)
      const color = nd?.color ?? 'rgba(255,255,255,0.3)'

      // Glow ring
      sel.append('circle')
        .attr('r', r + 8).attr('fill', 'none')
        .attr('stroke', color).attr('stroke-width', 1.5)
        .attr('opacity', nd ? 0.2 : 0)

      // Main circle
      sel.append('circle')
        .attr('r', r)
        .attr('fill', nd ? `${color}20` : 'rgba(255,255,255,0.03)')
        .attr('stroke', nd ? color : 'rgba(255,255,255,0.1)')
        .attr('stroke-width', nd ? 2 : 1.2)
        .attr('filter', nd ? 'url(#rglow)' : null)

      // Icon
      sel.append('text')
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
        .attr('font-size', isFinal ? 20 : 16)
        .attr('fill', nd ? color : 'rgba(255,255,255,0.2)')
        .attr('pointer-events', 'none')
        .text(nd ? nd.icon : '◌')

      // Label
      sel.append('text')
        .attr('text-anchor', 'middle')
        .attr('dy', r + 15)
        .attr('font-size', 10.5)
        .attr('font-family', "'JetBrains Mono', monospace")
        .attr('fill', nd ? `${color}cc` : 'rgba(255,255,255,0.15)')
        .attr('pointer-events', 'none')
        .text(nd ? nd.label : d.id.replace(/_/g,' '))

      // "Has output" dot
      if (nd) {
        sel.append('circle')
          .attr('cx', r - 4).attr('cy', -(r - 4))
          .attr('r', 4)
          .attr('fill', color)
          .attr('stroke', '#060101').attr('stroke-width', 1.5)
      }
    })

    svg.on('click', () => setSelected(null))

    sim.on('tick', () => {
      linkPaths.attr('d', (d: D3Link) => {
        const s = d.source as D3Node, t = d.target as D3Node
        const dr = Math.sqrt(((t.x ?? 0) - (s.x ?? 0)) ** 2 + ((t.y ?? 0) - (s.y ?? 0)) ** 2) * 1.3
        return `M${s.x},${s.y} A${dr},${dr} 0 0,1 ${t.x},${t.y}`
      })
      nodeG.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => { sim.stop() }
  }, [nodes])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <svg ref={svgRef} width="100%" height="100%" style={{ display: 'block' }} />

      {/* Legend */}
      <div style={{ position: 'absolute', bottom: 20, left: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#34d399', boxShadow: '0 0 8px #34d399' }} />
        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', fontFamily: "'JetBrains Mono',monospace" }}>Click node to view output · scroll to zoom · drag to pan</span>
      </div>

      {/* Output drawer */}
      {selected && (
        <>
          <div onClick={() => setSelected(null)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200, backdropFilter: 'blur(4px)' }} />
          <div style={{
            position: 'fixed', right: 0, top: 0, bottom: 0, zIndex: 201,
            width: 'min(580px, 100vw)',
            background: '#0c0c0c',
            borderLeft: `1px solid ${selected.color}35`,
            display: 'flex', flexDirection: 'column',
            boxShadow: `-24px 0 60px rgba(0,0,0,0.6), 0 0 40px ${selected.color}10`,
          }}>
            <div style={{ height: 2, background: `linear-gradient(90deg, ${selected.color}, ${selected.color}22)` }} />
            <div style={{ padding: '22px 26px 18px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 46, height: 46, borderRadius: 13, flexShrink: 0, background: `${selected.color}15`, border: `1px solid ${selected.color}35`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 21, color: selected.color }}>
                {selected.icon}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: "'Space Grotesk',sans-serif", fontWeight: 700, fontSize: 17, color: selected.color }}>{selected.label}</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.28)', marginTop: 2 }}>{selected.role}</div>
              </div>
              <button onClick={() => setSelected(null)}
                style={{ width: 30, height: 30, borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', fontSize: 15, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: '20px 26px' }}>
              <div className="report">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
