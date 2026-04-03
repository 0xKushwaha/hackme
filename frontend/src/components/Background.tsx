'use client'

import { useEffect, useRef } from 'react'

interface Particle {
  x: number; y: number
  vx: number; vy: number
  radius: number
  opacity: number
  pulse: number
  pulseSpeed: number
}

export default function Background() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let W = window.innerWidth
    let H = window.innerHeight
    let raf = 0
    let t = 0

    const resize = () => {
      W = window.innerWidth
      H = window.innerHeight
      canvas.width  = W
      canvas.height = H
    }
    resize()
    window.addEventListener('resize', resize)

    // ── Particles ──────────────────────────────────────────────────────
    const COUNT = Math.min(Math.floor((W * H) / 12000), 90)
    const particles: Particle[] = Array.from({ length: COUNT }, () => ({
      x:          Math.random() * W,
      y:          Math.random() * H,
      vx:         (Math.random() - 0.5) * 0.28,
      vy:         (Math.random() - 0.5) * 0.28,
      radius:     Math.random() * 1.4 + 0.4,
      opacity:    Math.random() * 0.5 + 0.15,
      pulse:      Math.random() * Math.PI * 2,
      pulseSpeed: Math.random() * 0.018 + 0.008,
    }))

    // ── Mouse ──────────────────────────────────────────────────────────
    const mouse = { x: W / 2, y: H / 2, active: false, brightness: 0 }
    const onMouseMove = (e: MouseEvent) => { mouse.x = e.clientX; mouse.y = e.clientY; mouse.active = true }
    const onMouseLeave = () => { mouse.active = false; mouse.brightness = 0 }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseleave', onMouseLeave)

    // ── Draw ───────────────────────────────────────────────────────────
    const CONNECT_DIST  = 130
    const MOUSE_DIST    = 160

    const draw = () => {
      ctx.clearRect(0, 0, W, H)

      // Deep radial background — dark navy
      const bg = ctx.createRadialGradient(W * 0.5, H * 0.3, 0, W * 0.5, H * 0.3, Math.max(W, H) * 0.85)
      bg.addColorStop(0,   'rgba(6,18,40,1)')
      bg.addColorStop(0.5, 'rgba(3,10,26,1)')
      bg.addColorStop(1,   'rgba(2,8,18,1)')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, W, H)

      t += 0.008

      // Smoothly ramp brightness up when mouse active, down when not
      mouse.brightness += mouse.active
        ? (1 - mouse.brightness) * 0.08
        : (0 - mouse.brightness) * 0.05
      const B = mouse.brightness  // 0 → 1

      // ── Moving grid ──────────────────────────────────────────────────
      const gridShift = (t * 18) % 60
      ctx.strokeStyle = 'rgba(20,60,160,0.05)'
      ctx.lineWidth = 0.5
      for (let x = -60 + (gridShift % 60); x < W + 60; x += 60) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
      }
      for (let y = -60 + (gridShift % 60); y < H + 60; y += 60) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
      }

      // ── Scan line ────────────────────────────────────────────────────
      const scanY = ((t * 60) % (H + 80)) - 40
      const scanGrad = ctx.createLinearGradient(0, scanY - 40, 0, scanY + 40)
      scanGrad.addColorStop(0,   'rgba(59,130,246,0)')
      scanGrad.addColorStop(0.5, 'rgba(59,130,246,0.04)')
      scanGrad.addColorStop(1,   'rgba(59,130,246,0)')
      ctx.fillStyle = scanGrad
      ctx.fillRect(0, scanY - 40, W, 80)

      // ── Update + draw particles ───────────────────────────────────────
      for (const p of particles) {
        p.x += p.vx; p.y += p.vy
        p.pulse += p.pulseSpeed
        if (p.x < -10) p.x = W + 10
        if (p.x > W + 10) p.x = -10
        if (p.y < -10) p.y = H + 10
        if (p.y > H + 10) p.y = -10

        // Mouse repulsion
        if (mouse.active) {
          const dx = p.x - mouse.x
          const dy = p.y - mouse.y
          const d  = Math.sqrt(dx * dx + dy * dy)
          if (d < MOUSE_DIST) {
            const f = (1 - d / MOUSE_DIST) * 0.012
            p.vx += (dx / d) * f
            p.vy += (dy / d) * f
          }
        }

        // Clamp velocity
        const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy)
        if (speed > 0.8) { p.vx = (p.vx / speed) * 0.8; p.vy = (p.vy / speed) * 0.8 }

        const pulse = 0.7 + Math.sin(p.pulse) * 0.3
        const boost = 1 + B * 2.2
        const finalOpacity = Math.min(1, p.opacity * pulse * boost)

        // Draw particle glow (grows on hover)
        const glowR = p.radius * (3 + B * 4)
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, glowR)
        grad.addColorStop(0, `rgba(100,160,255,${finalOpacity})`)
        grad.addColorStop(1, `rgba(59,130,246,0)`)
        ctx.beginPath()
        ctx.arc(p.x, p.y, glowR, 0, Math.PI * 2)
        ctx.fillStyle = grad
        ctx.fill()

        // Bright core
        const coreR = (140 + B * 80) | 0
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.radius * (1 + B * 0.6), 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${coreR},${coreR + 40},255,${finalOpacity})`
        ctx.fill()
      }

      // ── Draw connections ──────────────────────────────────────────────
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i]
        for (let j = i + 1; j < particles.length; j++) {
          const b   = particles[j]
          const dx  = a.x - b.x
          const dy  = a.y - b.y
          const d   = Math.sqrt(dx * dx + dy * dy)
          if (d > CONNECT_DIST) continue

          const alpha = (1 - d / CONNECT_DIST) * (0.22 + B * 0.4)
          const g = (130 + B * 40) | 0
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(b.x, b.y)
          ctx.strokeStyle = `rgba(59,${g},246,${alpha})`
          ctx.lineWidth = 0.7 + B * 0.6
          ctx.stroke()
        }

        // Mouse connections
        if (mouse.active) {
          const dx = a.x - mouse.x
          const dy = a.y - mouse.y
          const d  = Math.sqrt(dx * dx + dy * dy)
          if (d < MOUSE_DIST) {
            const alpha = (1 - d / MOUSE_DIST) * (0.4 + B * 0.5)
            ctx.beginPath()
            ctx.moveTo(a.x, a.y)
            ctx.lineTo(mouse.x, mouse.y)
            ctx.strokeStyle = `rgba(80,150,255,${alpha})`
            ctx.lineWidth   = 0.9 + B * 0.8
            ctx.stroke()
          }
        }
      }

      // ── Mouse cursor glow ─────────────────────────────────────────────
      if (B > 0.01) {
        const r1 = MOUSE_DIST * (1 + B * 0.5)
        const mg = ctx.createRadialGradient(mouse.x, mouse.y, 0, mouse.x, mouse.y, r1)
        mg.addColorStop(0,   `rgba(60,120,255,${0.10 * B})`)
        mg.addColorStop(0.4, `rgba(59,130,246,${0.06 * B})`)
        mg.addColorStop(1,   'rgba(59,130,246,0)')
        ctx.beginPath()
        ctx.arc(mouse.x, mouse.y, r1, 0, Math.PI * 2)
        ctx.fillStyle = mg
        ctx.fill()
      }

      // ── Vignette ─────────────────────────────────────────────────────
      const vig = ctx.createRadialGradient(W/2, H/2, H*0.3, W/2, H/2, H*0.85)
      vig.addColorStop(0, 'rgba(0,0,0,0)')
      vig.addColorStop(1, 'rgba(0,0,0,0.55)')
      ctx.fillStyle = vig
      ctx.fillRect(0, 0, W, H)

      raf = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseleave', onMouseLeave)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed', inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
        display: 'block',
      }}
    />
  )
}
