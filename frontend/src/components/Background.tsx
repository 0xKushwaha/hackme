'use client'

import { useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'

interface Stream {
  x: number
  y: number
  speed: number
  length: number
  chars: string[]
  fontSize: number
}

const CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%^&*()_+{}|:"<>?~`=[]\\;\',./'.split('')

const MONO = {
  bg:       ['rgba(10,10,10,1)', 'rgba(5,5,5,1)', 'rgba(0,0,0,1)'] as const,
  stream:   [190, 190, 195] as const, 
}

const CRIMSON = {
  bg:       ['rgba(22,4,8,1)', 'rgba(12,2,4,1)', 'rgba(7,0,2,1)'] as const,
  stream:   [232, 55, 88] as const,
}

export default function Background() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const modeRef   = useRef<'blue' | 'red'>('blue')
  const pathname  = usePathname()
  const [isBlurred, setIsBlurred] = useState(false)

  // Sync mode globally 
  useEffect(() => {
    const handler = (e: any) => { modeRef.current = e.detail }
    window.addEventListener('setAppMode', handler)
    return () => window.removeEventListener('setAppMode', handler)
  }, [])

  // Sync mode and blur from routing changes securely
  useEffect(() => {
    if (pathname?.includes('/red')) {
      modeRef.current = 'red'
      setIsBlurred(true)
    } else if (pathname?.includes('/run') || pathname?.includes('/analysis')) {
      modeRef.current = 'blue'
      setIsBlurred(true)
    } else {
      setIsBlurred(false)
    }
  }, [pathname])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    let W = window.innerWidth
    let H = window.innerHeight
    canvas.width = W
    canvas.height = H

    const resize = () => {
      W = window.innerWidth
      H = window.innerHeight
      canvas.width = W
      canvas.height = H
    }
    window.addEventListener('resize', resize)

    // ── High Performance Column-based Engine ────────────────────────
    // By assigning exact columns, we visually cover the ENTIRE background
    // and achieve immense density WITHOUT rendering thousands of hidden
    // overlapping streams that completely choke the framerate.
    
    let streams: Stream[] = []
    const FONT_SIZE = 14
    
    const initStreams = () => {
      const colCount = Math.floor(W / FONT_SIZE) + 2
      
      streams = Array.from({ length: colCount }, (_, i) => {
        const len = Math.floor(Math.random() * 25 + 10)
        return {
          x: i * FONT_SIZE,
          y: Math.random() * -H * 2.5,
          speed: (Math.random() * 1.5 + 0.8), // completely smooth float physics
          length: len,
          chars: Array.from({ length: len }, () => CHARS[Math.floor(Math.random() * CHARS.length)]),
          fontSize: FONT_SIZE
        }
      })
    }
    initStreams()

    let currentR = MONO.stream[0]
    let currentG = MONO.stream[1]
    let currentB = MONO.stream[2]
    
    let currentSpeedMult = 1.0

    let raf: number

    const draw = () => {
      const isRed = modeRef.current === 'red'
      const pal   = isRed ? CRIMSON : MONO

      // Background Rendering (Fast Radial Fill)
      const grad = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, Math.max(W, H))
      grad.addColorStop(0, pal.bg[0])
      grad.addColorStop(0.5, pal.bg[1])
      grad.addColorStop(1, pal.bg[2])
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, W, H)

      // Interpolations
      currentR += (pal.stream[0] - currentR) * 0.08
      currentG += (pal.stream[1] - currentG) * 0.08
      currentB += (pal.stream[2] - currentB) * 0.08
      const rgbColor = `${Math.round(currentR)},${Math.round(currentG)},${Math.round(currentB)}`
      
      const targetSpeed = isRed ? 3.0 : 1.0
      currentSpeedMult += (targetSpeed - currentSpeedMult) * 0.08

      // Main Text Render Settings
      ctx.textAlign = 'center'
      ctx.font = `700 ${FONT_SIZE}px "JetBrains Mono", monospace`

      for (let s of streams) {
        s.y += s.speed * currentSpeedMult

        // Glitch Effect
        if (Math.random() > 0.95) {
          const rIdx = Math.floor(Math.random() * s.chars.length)
          if (s.chars[rIdx]) {
            s.chars[rIdx] = CHARS[Math.floor(Math.random() * CHARS.length)]
          }
        }

        for (let i = 0; i < s.chars.length; i++) {
          const charText = s.chars[i]
          const charY = s.y - (i * s.fontSize)

          // V-Cull: Drop text operations out of bounds to maintain pure 144 FPS
          if (charY < -s.fontSize || charY > H + s.fontSize) {
            continue
          }

          const alpha = 1 - (i / s.length)
          if (alpha <= 0) continue

          if (i === 0) {
            if (isRed) {
              ctx.shadowBlur  = 6
              ctx.shadowColor = `rgba(232,55,88,0.85)`
            }
            ctx.fillStyle = `rgba(255, 255, 255, ${Math.max(0.6, alpha)})`
            if (isRed) { ctx.shadowBlur = 0; ctx.shadowColor = 'transparent' }
            // Expensive shadow blurs dropped entirely for maximum performance guarantee
            // Bright white contrast is enough for a clean crisp head visual
          } else {
            ctx.fillStyle = `rgba(${rgbColor}, ${isRed ? alpha * 0.92 : alpha * 0.85})`
          }

          ctx.fillText(charText, s.x, charY)
        }

        // Wrap Logic
        if (s.y - (s.length * s.fontSize) > H) {
          s.y = Math.random() * -H * 0.5
          // x is locked to its perfect column so we don't randomly stack columns over time
        }
      }

      raf = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: -1,
        filter: isBlurred ? 'blur(3px)' : 'none',
        opacity: isBlurred ? 0.55 : 1,
        transition: 'filter 1.2s cubic-bezier(0.4, 0, 0.2, 1), opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1)'
      }}
    />
  )
}
