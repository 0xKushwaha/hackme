'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

const COUNT = 140

interface Props { launching?: boolean }

export default function ParticleField({ launching = false }: Props) {
  const mountRef    = useRef<HTMLDivElement>(null)
  const launchRef   = useRef(false)
  const launchTRef  = useRef(0)
  const pickedRef   = useRef(-1)
  const posRef      = useRef<Float32Array | null>(null)

  // Sync prop → ref (safe bridge into Three.js loop)
  useEffect(() => {
    if (launching && !launchRef.current) {
      launchRef.current = true
      launchTRef.current = performance.now()
      if (posRef.current) {
        pickedRef.current = Math.floor(Math.random() * COUNT)
      }
    }
  }, [launching])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return
    let W = window.innerWidth, H = window.innerHeight

    const scene    = new THREE.Scene()
    const camera   = new THREE.PerspectiveCamera(65, W / H, 0.1, 100)
    camera.position.z = 13

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      return
    }
    renderer.setSize(W, H)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x000000, 0)
    mount.appendChild(renderer.domElement)

    // ── Particles ──────────────────────────────────────────────────
    const positions = new Float32Array(COUNT * 3)
    const colors    = new Float32Array(COUNT * 3)
    const velocities: { x: number; y: number; z: number }[] = []

    const c1 = new THREE.Color('#6366f1')
    const c2 = new THREE.Color('#06b6d4')
    const c3 = new THREE.Color('#a855f7')

    for (let i = 0; i < COUNT; i++) {
      positions[i*3]   = (Math.random() - 0.5) * 22
      positions[i*3+1] = (Math.random() - 0.5) * 22
      positions[i*3+2] = (Math.random() - 0.5) * 12
      velocities.push({
        x: (Math.random() - 0.5) * 0.007,
        y: (Math.random() - 0.5) * 0.007,
        z: (Math.random() - 0.5) * 0.003,
      })
      const t   = Math.random()
      const col = t < 0.45 ? c1 : t < 0.75 ? c2 : c3
      colors[i*3]   = col.r
      colors[i*3+1] = col.g
      colors[i*3+2] = col.b
    }

    posRef.current = positions
    // If launching was triggered before this effect ran, pick now
    if (launchRef.current && pickedRef.current < 0) {
      pickedRef.current = Math.floor(Math.random() * COUNT)
    }

    const ptGeo = new THREE.BufferGeometry()
    ptGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    ptGeo.setAttribute('color',    new THREE.BufferAttribute(colors, 3))
    const ptMat = new THREE.PointsMaterial({
      vertexColors: true, size: 0.08, transparent: true, opacity: 0.75, sizeAttenuation: true,
    })
    scene.add(new THREE.Points(ptGeo, ptMat))

    // ── Connection lines ───────────────────────────────────────────
    const MAX_LINES   = 350
    const linePos     = new Float32Array(MAX_LINES * 2 * 3)
    const linePosAttr = new THREE.BufferAttribute(linePos, 3)
    linePosAttr.setUsage(THREE.DynamicDrawUsage)
    const lineGeo = new THREE.BufferGeometry()
    lineGeo.setAttribute('position', linePosAttr)
    lineGeo.setDrawRange(0, 0)
    const lineMat = new THREE.LineBasicMaterial({ color: 0x6366f1, transparent: true, opacity: 0.18 })
    scene.add(new THREE.LineSegments(lineGeo, lineMat))

    // ── Launch: selected-node glow sphere ──────────────────────────
    const glowMat  = new THREE.MeshBasicMaterial({ color: 0x6366f1, transparent: true, opacity: 0 })
    const glowMesh = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 16), glowMat)
    scene.add(glowMesh)

    // Point light that follows the picked node
    const pickLight = new THREE.PointLight(0x6366f1, 0, 5)
    scene.add(pickLight)

    // 4 expanding rings
    const ringMats: THREE.MeshBasicMaterial[] = []
    const ringMeshes: THREE.Mesh[] = []
    for (let r = 0; r < 4; r++) {
      const mat  = new THREE.MeshBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0, side: THREE.DoubleSide })
      const mesh = new THREE.Mesh(new THREE.RingGeometry(0.3, 0.38, 48), mat)
      scene.add(mesh)
      ringMats.push(mat)
      ringMeshes.push(mesh)
    }

    // ── Mouse parallax ─────────────────────────────────────────────
    let mx = 0, my = 0
    const onMouseMove = (e: MouseEvent) => {
      mx = (e.clientX / W - 0.5) * 2
      my = -(e.clientY / H - 0.5) * 2
    }
    window.addEventListener('mousemove', onMouseMove)

    const onResize = () => {
      W = window.innerWidth; H = window.innerHeight
      camera.aspect = W / H
      camera.updateProjectionMatrix()
      renderer.setSize(W, H)
    }
    window.addEventListener('resize', onResize)

    // ── Animate ────────────────────────────────────────────────────
    const THRESH = 5.0
    let raf: number

    const tick = () => {
      raf = requestAnimationFrame(tick)

      for (let i = 0; i < COUNT; i++) {
        positions[i*3]   += velocities[i].x
        positions[i*3+1] += velocities[i].y
        positions[i*3+2] += velocities[i].z
        if (positions[i*3]   >  11) positions[i*3]   = -11
        if (positions[i*3]   < -11) positions[i*3]   =  11
        if (positions[i*3+1] >  11) positions[i*3+1] = -11
        if (positions[i*3+1] < -11) positions[i*3+1] =  11
        if (positions[i*3+2] >   6) positions[i*3+2] =  -6
        if (positions[i*3+2] <  -6) positions[i*3+2] =   6
      }
      ptGeo.attributes.position.needsUpdate = true

      let lc = 0
      for (let i = 0; i < COUNT && lc < MAX_LINES - 1; i++) {
        for (let j = i + 1; j < COUNT && lc < MAX_LINES - 1; j++) {
          const dx = positions[i*3]   - positions[j*3]
          const dy = positions[i*3+1] - positions[j*3+1]
          const dz = positions[i*3+2] - positions[j*3+2]
          if (dx*dx + dy*dy + dz*dz < THRESH*THRESH) {
            linePos[lc*6+0] = positions[i*3];   linePos[lc*6+1] = positions[i*3+1]; linePos[lc*6+2] = positions[i*3+2]
            linePos[lc*6+3] = positions[j*3];   linePos[lc*6+4] = positions[j*3+1]; linePos[lc*6+5] = positions[j*3+2]
            lc++
          }
        }
      }
      lineGeo.setDrawRange(0, lc * 2)
      lineGeo.attributes.position.needsUpdate = true

      camera.position.x += (mx * 1.2 - camera.position.x) * 0.018
      camera.position.y += (my * 1.2 - camera.position.y) * 0.018
      camera.lookAt(0, 0, 0)

      // ── Launch animation ───────────────────────────────────────
      if (launchRef.current) {
        const pi = pickedRef.current
        if (pi >= 0) {
          const elapsed = (performance.now() - launchTRef.current) / 1000
          const px = positions[pi*3], py = positions[pi*3+1], pz = positions[pi*3+2]

          // Glow sphere on selected node
          glowMesh.position.set(px, py, pz)
          glowMat.opacity      = Math.min(elapsed * 5, 1.0)
          glowMesh.scale.setScalar(1 + elapsed * 1.2)

          // Point light
          pickLight.position.set(px, py, pz)
          pickLight.intensity = Math.min(elapsed * 3, 2.5)

          // 4 rings expanding outward with staggered starts
          ringMeshes.forEach((ring, ri) => {
            const t = Math.max(0, elapsed - ri * 0.10)
            ring.position.set(px, py, pz)
            ring.lookAt(camera.position)
            ring.scale.setScalar(1 + t * 5)
            ringMats[ri].opacity = Math.max(0, 0.75 - t * 0.6)
          })

          // Brighten whole network
          lineMat.opacity = Math.min(0.18 + elapsed * 0.5, 0.7)
          ptMat.opacity   = Math.min(0.75 + elapsed * 0.35, 1.0)
        }
      }

      renderer.render(scene, camera)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf)
      posRef.current = null
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={mountRef} style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }} />
}
