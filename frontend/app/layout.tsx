import type React from "react"
import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"
import { Space_Grotesk } from "next/font/google"
import "./globals.css"
import { TranslationProvider } from "@/lib/i18n"
import { Suspense } from "react"

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
})

export const metadata: Metadata = {
  title: "easyPLU solver",
  description: "Sign in and track your easyPLU progress.",
  icons: {
    icon: { url: "/easyplu-icon.png", type: "image/png" },
    apple: "/easyplu-icon.png",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`font-sans ${GeistSans.variable} ${GeistMono.variable} ${spaceGrotesk.variable}`}>
        <TranslationProvider><Suspense>{children}</Suspense></TranslationProvider>
      </body>
    </html>
  )
}
