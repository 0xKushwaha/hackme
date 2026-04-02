'use client'

import React, { useState, useEffect } from 'react'
import { Canvas, CanvasProps } from '@react-three/fiber'

function checkWebGL(): boolean {
  try {
    const c = document.createElement('canvas')
    const ctx = c.getContext('webgl2') ?? c.getContext('webgl')
    if (!ctx) return false
    const ext = (ctx as WebGLRenderingContext).getExtension('WEBGL_lose_context')
    ext?.loseContext()
    return true
  } catch {
    return false
  }
}

export default function CanvasSafe({ children, ...props }: CanvasProps & { children: React.ReactNode }) {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (checkWebGL()) setReady(true)
  }, [])

  if (!ready) return null

  return (
    <Canvas
      {...props}
      gl={{
        powerPreference: 'high-performance',
        antialias: true,
        alpha: false,
        failIfMajorPerformanceCaveat: false,
        ...(props.gl as object | undefined),
      }}
      onCreated={(state) => {
        state.gl.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      }}
    >
      {children}
    </Canvas>
  )
}
