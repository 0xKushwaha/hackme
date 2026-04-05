import type { Metadata } from 'next'
import './globals.css'
import GlobalBackground from '@/components/GlobalBackground'
import PageTransition from '@/components/PageTransition'

export const metadata: Metadata = {
  title: 'Hackme',
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
        <GlobalBackground />
        <PageTransition>
          {children}
        </PageTransition>
      </body>
    </html>
  )
}
