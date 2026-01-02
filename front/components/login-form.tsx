"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { X, Eye, EyeOff, Wifi, WifiOff, RefreshCw } from "lucide-react"

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

type ApiStatus = "checking" | "online" | "offline" | "error"

export function LoginForm() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [targetScore, setTargetScore] = useState<number | undefined>(undefined)
  const [showCustomResult, setShowCustomResult] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [currentMessage, setCurrentMessage] = useState<string>("")
  const [currentStage, setCurrentStage] = useState<string>("")
  const [progress, setProgress] = useState<number>(0)
  const [submittedItems, setSubmittedItems] = useState<{ current: number; total: number } | null>(null)
  const [attempt, setAttempt] = useState<number>(0)
  const [currentKnowledge, setCurrentKnowledge] = useState<number | null>(null)
  const [result, setResult] = useState<SessionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showBackground, setShowBackground] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking")

  useEffect(() => {
    const isHelena = email.toLowerCase().includes("helena")
    setShowBackground(isHelena)
    document.body.classList.toggle("helena-cursor", isHelena)
  }, [email])

  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        setApiStatus("checking")
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 5000)

        const response = await fetch("http://localhost:8000/health", {
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (response.ok) {
          setApiStatus("online")
        } else {
          setApiStatus("error")
        }
      } catch (err) {
        setApiStatus("offline")
      }
    }

    checkApiHealth()
    const interval = setInterval(checkApiHealth, 30000) // Check every 30 seconds

    return () => clearInterval(interval)
  }, [])

  const handleEasyPLULogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsRunning(true)
    setResult(null)
    setError(null)
    setProgress(0)
    setCurrentStage("")
    setCurrentMessage("")
    setSubmittedItems(null)
    setAttempt(0)
    setCurrentKnowledge(null)

    try {
      const response = await fetch("http://localhost:8000/run-session-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          email, 
          password, 
          target_score: targetScore,
          full_knowledge: true 
        }),
      })

      if (response.status === 401) {
        setError("Napačni podatki, preveri geslo ali uporabniško ime!")
        setIsRunning(false)
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error("No response body")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6))
              
              setCurrentStage(data.stage || "")
              setCurrentMessage(data.message || "")
              setProgress(data.progress || 0)

              // Update attempt and knowledge if provided
              if (data.attempt !== undefined) {
                setAttempt(data.attempt)
              }
              if (data.user_knowledge !== undefined && data.user_knowledge !== null) {
                setCurrentKnowledge(data.user_knowledge)
              }

              if (data.submitted !== undefined && data.total_items !== undefined) {
                setSubmittedItems({ current: data.submitted, total: data.total_items })
              } else if (data.stage !== "submitting_answers") {
                setSubmittedItems(null)
              }

              if (data.stage === "final" && data.result) {
                setResult(data.result)
                setIsRunning(false)
                return
              }

              if (data.stage === "error") {
                setError(data.message || data.error || "Neznana napaka")
                setIsRunning(false)
                return
              }
            } catch (parseError) {
              console.error("Error parsing SSE data:", parseError)
            }
          }
        }
      }
    } catch (err: any) {
      if (err.message && err.message.includes("401")) {
        setError("Napačni podatki, preveri geslo ali uporabniško ime!")
      } else {
        setError(err.message || "Napaka pri povezovanju s strežnikom")
      }
      setIsRunning(false)
    }
  }

  const getStageLabel = (stage: string): string => {
    const stageLabels: Record<string, string> = {
      initializing: "Začenjanje",
      logging_in: "Prijavljanje",
      storing_plus: "Shranjevanje PLU podatkov",
      creating_session: "Ustvarjanje seje",
      starting_execution: "Zaganjanje izvajanja",
      fetching_items: "Pridobivanje elementov",
      submitting_answers: "Oddajanje odgovorov",
      submitting_result: "Oddajanje rezultata",
      completed: "Končano",
      error: "Napaka",
      attempt_start: "Začenjanje poskusa",
      attempt_complete: "Poskus končan",
      retrying: "Ponovno poskušanje",
    }
    return stageLabels[stage] || stage
  }

  const getStatusConfig = () => {
    switch (apiStatus) {
      case "checking":
        return {
          icon: RefreshCw,
          text: "Preverjanje API...",
          bgColor: "bg-yellow-100 dark:bg-yellow-950/30",
          textColor: "text-yellow-800 dark:text-yellow-300",
          borderColor: "border-yellow-300 dark:border-yellow-700",
          iconClass: "animate-spin",
        }
      case "online":
        return {
          icon: Wifi,
          text: "API Povezan",
          bgColor: "bg-green-100 dark:bg-green-950/30",
          textColor: "text-green-800 dark:text-green-300",
          borderColor: "border-green-300 dark:border-green-700",
          iconClass: "",
        }
      case "offline":
        return {
          icon: WifiOff,
          text: "API Nedostopen",
          bgColor: "bg-red-100 dark:bg-red-950/30",
          textColor: "text-red-800 dark:text-red-300",
          borderColor: "border-red-300 dark:border-red-700",
          iconClass: "",
        }
      case "error":
        return {
          icon: WifiOff,
          text: "API Napaka",
          bgColor: "bg-orange-100 dark:bg-orange-950/30",
          textColor: "text-orange-800 dark:text-orange-300",
          borderColor: "border-orange-300 dark:border-orange-700",
          iconClass: "",
        }
    }
  }

  const statusConfig = getStatusConfig()
  const StatusIcon = statusConfig.icon

  return (
    <>
      {!showBackground && <div className="fixed inset-0 bg-white z-0" style={{ pointerEvents: "none" }} />}
      <Card className="w-full max-w-md relative z-10 mx-4 sm:mx-0">
        <CardHeader className="space-y-1 text-center px-4 sm:px-6">
          <CardTitle className="text-2xl sm:text-3xl font-title font-bold tracking-tight">easyPLU solver</CardTitle>
          <div className="flex justify-center pt-2">
            <div
              className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${statusConfig.bgColor} ${statusConfig.borderColor} transition-all duration-300`}
            >
              <StatusIcon className={`w-4 h-4 ${statusConfig.textColor} ${statusConfig.iconClass}`} />
              <span className={`text-xs font-medium ${statusConfig.textColor}`}>{statusConfig.text}</span>
            </div>
          </div>
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

              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-11 pr-10"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors"
                  aria-label={showPassword ? "Skrij geslo" : "Prikaži geslo"}
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
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
              <div className="w-full space-y-3">
                {/* Stage indicator */}
                {currentStage && (
                  <div className="text-center">
                    <p className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                      {getStageLabel(currentStage)}
                    </p>
                    {currentMessage && (
                      <p className="text-xs text-gray-600 dark:text-gray-400">{currentMessage}</p>
                    )}
                    {/* Attempt and knowledge info */}
                    {(attempt > 0 || currentKnowledge !== null) && (
                      <div className="flex items-center justify-center gap-3 mt-2">
                        {attempt > 0 && (
                          <span className="text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/30 px-2 py-1 rounded">
                            Poskus: {attempt}
                          </span>
                        )}
                        {currentKnowledge !== null && (
                          <span className="text-xs font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/30 px-2 py-1 rounded">
                            Znanje: {currentKnowledge.toFixed(2)}%
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Progress bar */}
                <div className="w-full space-y-2">
                  <Progress value={progress} className="h-2" />
                  <div className="flex justify-between items-center text-xs text-gray-600 dark:text-gray-400">
                    <span>{Math.round(progress)}%</span>
                    {submittedItems && (
                      <span>
                        Oddano: {submittedItems.current} / {submittedItems.total}
                      </span>
                    )}
                  </div>
                </div>

                {/* Loading spinner */}
                <div className="flex justify-center pt-2">
                  <div className="relative w-12 h-12">
                    <div className="absolute inset-0 rounded-full border-4 border-gray-200 dark:border-gray-700"></div>
                    <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 border-r-blue-500 animate-spin"></div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {result && (
            <div className="mt-4 p-3 rounded-lg bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 border border-green-200 dark:border-green-800 space-y-2 relative">
              <button
                onClick={() => setResult(null)}
                className="absolute top-2 right-2 p-1 rounded-full hover:bg-green-100 dark:hover:bg-green-900/50 transition-colors touch-manipulation"
                aria-label="Zapri rezultate"
              >
                <X className="w-4 h-4 text-green-700 dark:text-green-300" />
              </button>

              <div className="flex items-center gap-2 pb-1.5 border-b border-green-100 dark:border-green-800">
                <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-sm font-semibold text-green-900 dark:text-green-100">
                  Test uspešno zaključen
                </h3>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                  <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Rezultat</p>
                  <p className="text-base font-bold text-green-700 dark:text-green-400">
                    {result.final_result.toFixed(1)}%
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                  <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Znanje</p>
                  <p className="text-base font-bold text-green-700 dark:text-green-400">
                    {result.user_knowledge.toFixed(1)}%
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                  <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Točke</p>
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                    {result.total_user_points}/{result.max_points}
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                  <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Uvrstitev</p>
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                    #{result.user_ranking_in_store}
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                  <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Gold Plus</p>
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                    {result.earned_gold_plus}/{result.total_gold_plus}
                  </p>
                </div>

                <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                  <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Elementi</p>
                  <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                    {result.plu_execution_session_item_count}
                  </p>
                </div>
              </div>

              <div className="bg-white/60 dark:bg-white/5 rounded p-2 border border-green-100 dark:border-green-800">
                <p className="text-[10px] text-gray-600 dark:text-gray-400 mb-0.5">Čas izvajanja</p>
                <p className="text-sm font-semibold text-gray-800 dark:text-gray-200">{result.total_execution_time}s</p>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 p-4 rounded-lg bg-red-50 border border-red-200">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path fillRule="evenodd" d="M6 18L18 6M6 6l12 12" clipRule="evenodd" />
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
                  d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.387.6.112.82-.262.82-.583 0-.288-.01-1.05-.015-2.06-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.09-.746.083-.73.083-.73 1.205.084 1.84 1.238 1.84 1.238 1.07 1.834 2.807 1.304 3.492.997.108-.776.418-1.304.762-1.604-2.665-.304-5.466-1.332-5.466-5.933 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.3 1.23a11.5 11.5 0 013.003-.404c1.018.004 2.045.137 3.003.404 2.29-1.552 3.296-1.23 3.296-1.23.655 1.653.243 2.873.12 3.176.77.84 1.233 1.91 1.233 3.22 0 4.61-2.807 5.625-5.478 5.922.43.372.823 1.102.823 2.222 0 .324.218.7.825.582C20.565 21.796 24 17.297 24 12c0-6.63-5.37-12-12-12z"
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
