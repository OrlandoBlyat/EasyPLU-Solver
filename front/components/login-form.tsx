"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { X } from "lucide-react"

interface SessionResult {
  final_result: number
  total_user_points: number
  max_points: number
  required_points: number
  user_knowledge: number
  user_ranking_in_store: number
  earned_gold_plus: number
  total_gold_plus: number
  plu_execution_session_item_count: number
  total_execution_time: number
}

export function LoginForm() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [targetScore, setTargetScore] = useState<number | undefined>(undefined)
  const [showCustomResult, setShowCustomResult] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [currentMessage, setCurrentMessage] = useState<string>("")
  const [result, setResult] = useState<SessionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showBackground, setShowBackground] = useState(false)

  useEffect(() => {
    const isHelena = email.toLowerCase().includes("helena")
    setShowBackground(isHelena)
    document.body.classList.toggle("helena-cursor", isHelena);
  }, [email])

  const handleEasyPLULogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsRunning(true)
    setResult(null)
    setError(null)

    try {
      // Step 0: API OK
      setCurrentMessage("API OK")
      await new Promise((r) => setTimeout(r, 500))

      // Step 1: Logging in
      setCurrentMessage("Prijavljanje")
      const response = await fetch("http://localhost:8000/run-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, target_score: targetScore }),
      })

      if (response.status === 401) {
        setError("Napačni podatki, preveri geslo ali uporabniško ime!")
        setIsRunning(false)
        setCurrentMessage("")
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      if (data.status !== "success") throw new Error(data.detail || "Session failed")

      // Step 2: Solving Test
      setCurrentMessage("Reševanje testa")
      await new Promise((r) => setTimeout(r, 800))

      // Step 3: Done
      setCurrentMessage("Končano")
      await new Promise((r) => setTimeout(r, 300))

      setResult(data.data)
    } catch (err: any) {
      if (err.message && err.message.includes("401")) {
        setError("Napačni podatki, preveri geslo ali uporabniško ime!")
      } else {
        setError(err.message)
      }
    } finally {
      setIsRunning(false)
      setCurrentMessage("")
    }
  }

  return (
    <>
      {!showBackground && <div className="fixed inset-0 bg-white z-0" style={{ pointerEvents: "none" }} />}
      <Card className="w-full max-w-md relative z-10 mx-4 sm:mx-0">
        <CardHeader className="space-y-1 text-center px-4 sm:px-6">
          <CardTitle className="text-2xl sm:text-3xl font-title font-bold tracking-tight">easyPLU solver</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6 px-4 sm:px-6">
          <form onSubmit={handleEasyPLULogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium px-1">
                Uporabniško ime (e-naslov)
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="ime@primer.si"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-11"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium px-1">
                Geslo
              </Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-11"
              />
            </div>

            <div className="flex items-center space-x-2 px-1">
              <input
                type="checkbox"
                id="customResult"
                checked={showCustomResult}
                onChange={(e) => setShowCustomResult(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <Label htmlFor="customResult" className="text-sm font-medium cursor-pointer">
                Rezultat po meri
              </Label>
            </div>

            {showCustomResult && (
              <div className="relative">
                <Input
                  id="targetScore"
                  type="number"
                  placeholder="Rezultat"
                  value={targetScore ?? ""}
                  onChange={(e) => setTargetScore(e.target.value ? Number(e.target.value) : undefined)}
                  className="h-11 pr-8"
                  min="0"
                  max="100"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">%</span>
              </div>
            )}

            <div className="space-y-3 pt-2">
              <p className="text-sm text-muted-foreground text-center py-2">Prijavite se z</p>
              <div className="flex flex-row gap-3">
                <Button type="submit" size="lg" className="flex-1 font-medium cursor-pointer" disabled={isRunning}>
                  easyPLU
                </Button>
                <Button
                  type="button"
                  size="lg"
                  variant="secondary"
                  className="flex-1 font-medium cursor-not-allowed opacity-60"
                  disabled
                >
                  Lidl SSO
                </Button>
              </div>
            </div>
          </form>

          {isRunning && (
            <div className="flex flex-col items-center justify-center py-8 space-y-4">
              <div className="relative w-16 h-16">
                <div className="absolute inset-0 rounded-full border-4 border-gray-200"></div>
                <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 border-r-blue-500 animate-spin"></div>
                <div className="absolute inset-2 rounded-full bg-blue-100 animate-pulse"></div>
              </div>
              <p className="text-sm font-medium text-gray-700 animate-pulse">{currentMessage}</p>
            </div>
          )}

          {result && (
            <div className="mt-4 p-4 sm:p-6 rounded-lg bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 border border-green-200 dark:border-green-800 space-y-4 relative">
              <button
                onClick={() => setResult(null)}
                className="absolute top-2 right-2 sm:top-3 sm:right-3 p-1 rounded-full hover:bg-green-100 dark:hover:bg-green-900/50 transition-colors touch-manipulation"
                aria-label="Zapri rezultate"
              >
                <X className="w-5 h-5 text-green-700 dark:text-green-300" />
              </button>

              <div className="flex items-center gap-2 pb-2 border-b border-green-100 dark:border-green-800">
                <div className="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-base sm:text-lg font-semibold text-green-900 dark:text-green-100">
                  Test uspešno zaključen
                </h3>
              </div>

              <div className="grid grid-cols-1 xs:grid-cols-2 gap-3">
                <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Končni rezultat</p>
                  <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                    {result.final_result.toFixed(2)}%
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Znanje uporabnika</p>
                  <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                    {result.user_knowledge.toFixed(2)}%
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Pridobljene točke</p>
                  <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                    {result.total_user_points} / {result.max_points}
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Uvrstitev v trgovini</p>
                  <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                    #{result.user_ranking_in_store}
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Gold Plus</p>
                  <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                    {result.earned_gold_plus} / {result.total_gold_plus}
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Opravljeni elementi</p>
                  <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">
                    {result.plu_execution_session_item_count}
                  </p>
                </div>
              </div>

              <div className="bg-white/60 dark:bg-white/5 rounded-lg p-3 border border-green-100 dark:border-green-800">
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Skupni čas izvajanja</p>
                <p className="text-lg font-semibold text-gray-800 dark:text-gray-200">{result.total_execution_time}s</p>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 p-4 rounded-lg bg-red-50 border border-red-200">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <p className="text-sm text-red-700 font-medium">Napaka: {error}</p>
              </div>
            </div>
          )}

          <div className="flex flex-col items-center gap-2 pt-4 border-t border-gray-100">
            <a
              href="https://github.com/OrlandoBlyat/EasyPLU-Solver"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-gray-700 hover:text-black transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                <path
                  fillRule="evenodd"
                  d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.387.6.112.82-.262.82-.583 0-.288-.01-1.05-.015-2.06-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.09-.746.083-.73.083-.73 1.205.084 1.84 1.238 1.84 1.238 1.07 1.834 2.807 1.304 3.492.997.108-.776.418-1.304.762-1.604-2.665-.304-5.466-1.332-5.466-5.933 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.3 1.23a11.5 11.5 0 013.003-.404c1.018.004 2.045.137 3.003.404 2.29-1.552 3.296-1.23 3.296-1.23.655 1.653.243 2.873.12 3.176.77.84 1.233 1.91 1.233 3.22 0 4.61-2.807 5.625-5.478 5.922.43.372.823 1.102.823 2.222 0 1.604-.015 2.896-.015 3.287 0 .324.218.7.825.582C20.565 21.796 24 17.297 24 12c0-6.63-5.37-12-12-12z"
                  clipRule="evenodd"
                />
              </svg>
            </a>
            <p className="text-xs text-gray-500 text-center">© 2025 Orlando Dlugoš Čeh</p>
          </div>
        </CardContent>
      </Card>
    </>
  )
}
