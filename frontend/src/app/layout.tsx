import type { Metadata } from 'next'
import './globals.css'
import dynamic from 'next/dynamic'

const Background = dynamic(() => import('@/components/Background'), { ssr: false })

export const metadata: Metadata = {
  title: 'DS Agent Team',
  description: 'Autonomous · Adaptive · Intelligent',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Background />
        {children}
      </body>
    </html>
  )
}
