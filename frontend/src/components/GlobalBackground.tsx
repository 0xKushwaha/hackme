'use client'

import dynamic from 'next/dynamic'

const Background = dynamic(() => import('./Background'), { ssr: false })

export default function GlobalBackground() {
  return <Background />
}
