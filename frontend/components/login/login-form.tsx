"use client"

import { useTranslation } from "@/lib/i18n"
import type React from "react"
import type { SessionResult } from "@/lib/client/session-types"
import { SessionResultCard } from "@/components/login/session-result"
import debugConfig from "../../../config/debug-config.json"
import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { FooterTools } from "@/components/layout/footer-tools"
import { PasswordField } from "@/components/login/password-field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import Image from "next/image"
import { RunProgress } from "@/components/login/run-progress"
import { Wifi, WifiOff, ArrowRight } from "lucide-react"

type ApiStatus = "checking" | "online" | "offline" | "error"

const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()) && value.trim().length <= 254

export function LoginForm({ initialApiStatus = "checking" }: { initialApiStatus?: ApiStatus }) {
  const { t } = useTranslation()
  const [email, setEmail] = useState("")
  const [showUsernameWarning, setShowUsernameWarning] = useState(false)
  const [password, setPassword] = useState("")
  const [showPasswordWarning, setShowPasswordWarning] = useState(false)
  const [targetScore, setTargetScore] = useState<number | undefined>(undefined)
  const [showCustomResult, setShowCustomResult] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [mode, setMode] = useState<"knowledge" | "tasks">("knowledge")
  const [taskProgress, setTaskProgress] = useState<{ completed: number; total: number } | null>(null)
  const [testStarted, setTestStarted] = useState(false)
  const [otpRequested, setOtpRequested] = useState(false)
  const [currentMessage, setCurrentMessage] = useState<string>("")
  const [currentMessageKey, setCurrentMessageKey] = useState<string | null>(null)
  const [currentMessageParams, setCurrentMessageParams] = useState<Record<string, string | number>>({})
  const [currentStage, setCurrentStage] = useState<string>("")
  const [queuedAt, setQueuedAt] = useState<number | null>(null)
  const [queueSeconds, setQueueSeconds] = useState(0)
  const runController = useRef<AbortController | null>(null)
  const [submittedItems, setSubmittedItems] = useState<{ current: number; total: number } | null>(null)
  const [currentKnowledge, setCurrentKnowledge] = useState<number | null>(null)
  const [result, setResult] = useState<SessionResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showBackground, setShowBackground] = useState(false)
  const [apiStatus, setApiStatus] = useState<ApiStatus>(initialApiStatus)
  const [otp, setOtp] = useState("")
  const [runId, setRunId] = useState<string | null>(null)
  const [otpSubmitting, setOtpSubmitting] = useState(false)

  useEffect(() => () => runController.current?.abort(), [])
  useEffect(() => {
    if (currentStage !== "queued" || queuedAt === null) return
    const update = () => setQueueSeconds(Math.floor((Date.now() - queuedAt) / 1000))
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [currentStage, queuedAt])

  useEffect(() => {
    const isHelena = email.toLowerCase().includes("helena")
    setShowBackground(isHelena)
    document.body.classList.toggle("helena-cursor", isHelena)
  }, [email])

  useEffect(() => {
    let active = true
    let controller: AbortController | null = null
    const checkApiHealth = async () => {
      controller = new AbortController()
      const timeoutId = setTimeout(() => controller?.abort(), 5000)
      try {
        const response = await fetch("/api/backend/health", {
          signal: controller.signal,
          cache: "no-store",
        })
        if (active) setApiStatus(response.ok ? "online" : "error")
      } catch (err) {
        if (active) setApiStatus("offline")
      } finally {
        clearTimeout(timeoutId)
      }
    }

    if (initialApiStatus !== "online") checkApiHealth()
    const interval = setInterval(checkApiHealth, 30000) // Check every 30 seconds

    return () => {
      active = false
      controller?.abort()
      clearInterval(interval)
    }
  }, [initialApiStatus])

  const startSession = async (loginMethod: "easyplu" | "sso") => {
    const controller = new AbortController()
    runController.current = controller
    // Capture the request before clearing the visible credential field.
    const body = JSON.stringify({
      email,
      password,
      target_score: mode === "knowledge" && showCustomResult ? targetScore : undefined,
      full_knowledge: mode === "knowledge",
      mode,
      login_method: loginMethod,
    })
    setPassword("")
    setShowPasswordWarning(false)
    setIsRunning(true)
    setTaskProgress(null)
    setTestStarted(false)
    setOtpRequested(false)
    setResult(null)
    setError(null)
    setCurrentStage("")
    setCurrentMessage("")
    setCurrentMessageKey(null)
    setCurrentMessageParams({})
    setQueuedAt(null)
    setQueueSeconds(0)
    setSubmittedItems(null)
    setCurrentKnowledge(null)
    setOtp("")
    setRunId(null)

    try {
      const response = await fetch("/api/backend/run-session-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        signal: controller.signal,
      })

      if (response.status === 401) {
        setError(t("Incorrect credentials. Check your password or username!"))
        setIsRunning(false)
        return
      }

      if (!response.ok) {
        if (response.status === 429) {
          const data = await response.json()
          throw new Error(data.detail || t("The server is busy. Please try again later."))
        }
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
        if (controller.signal.aborted) return
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.stage === "otp_required") setOtpRequested(true)
              if (["creating_session", "starting_execution", "fetching_items", "submitting_answers", "submitting_result", "completed"].includes(data.stage)) {
                setTestStarted(true)
              }
              if (data.run_id) setRunId(data.run_id)
              if (data.tasks_total !== undefined) {
                setTaskProgress({ completed: data.tasks_completed, total: data.tasks_total })
                setTestStarted(true)
              }
              if (data.stage === "closed") {
                throw new Error(t("The connection closed before the test finished. Please try again."))
              }
              
              setCurrentStage(data.stage || "")
              setCurrentMessage(data.message || "")
              setCurrentMessageKey(data.message_key || null)
              setCurrentMessageParams(data.message_params || {})
              if (data.stage === "queued") setQueuedAt(previous => previous ?? Date.now())
              else setQueuedAt(null)

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
                setEmail("")
                setPassword("")
                setTargetScore(undefined)
                setShowCustomResult(false)
                setShowUsernameWarning(false)
                setShowPasswordWarning(false)
                setOtp("")
                setRunId(null)
                setMode("knowledge")
                setIsRunning(false)
                return
              }

              if (data.stage === "error") {
                setError(data.message_key ? t(data.message_key, data.message_params) : data.message || data.error || t("Unknown error"))
                setIsRunning(false)
                return
              }
            } catch (parseError) {
              if (parseError instanceof Error && !(parseError instanceof SyntaxError)) {
                throw parseError
              }
              if (process.env.NODE_ENV === "development" && debugConfig.enabled && debugConfig.frontend) {
                console.error("[EasyPLU] Invalid progress event:", parseError)
              }
            }
          }
        }
      }
      throw new Error(t("The connection was interrupted before the test finished. Please try again."))
    } catch (err: any) {
      if (controller.signal.aborted) return
      if (err.message && err.message.includes("401")) {
        setError(t("Incorrect credentials. Check your password or username!"))
      } else {
        setError(err.message || t("Error connecting to the server"))
      }
      setIsRunning(false)
    } finally {
      if (runController.current === controller) runController.current = null
    }
  }

  const cancelQueuedRun = () => {
    runController.current?.abort()
    runController.current = null
    setIsRunning(false)
    setCurrentStage("")
    setQueuedAt(null)
    setCurrentMessage("")
    setCurrentMessageKey(null)
  }

  const handleEasyPLULogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isEmail(email) || password.length < 8) return
    await startSession("easyplu")
  }

  const handleSsoLogin = async () => {
    if (!/^[0-9]{8}$/.test(email.trim()) || password.length < 8) {
      setError(t("Enter your eight-digit global number and password"))
      return
    }
    await startSession("sso")
  }

  const handleSubmitOtp = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!runId || !/^[0-9]{6}$/.test(otp) || otpSubmitting) return

    setOtpSubmitting(true)
    setError(null)
    try {
      const response = await fetch("/api/backend/submit-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: runId, otp }),
      })
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || `HTTP error! status: ${response.status}`)
      }
      setOtp("")
      setCurrentStage((stage) => stage === "otp_required" ? "logging_in" : stage)
      setCurrentMessage(t("SMS code sent, waiting to sign in..."))
      setCurrentMessageKey(null)
    } catch (err: any) {
      setError(err.message || t("Error sending the SMS code"))
    } finally {
      setOtpSubmitting(false)
    }
  }

  const showRunPanel = isRunning && (testStarted || otpRequested)
  const isSsoUsername = /^\d{8}$/.test(email.trim())
  const isEmailUsername = isEmail(email)
  const usernameInvalid = showUsernameWarning && Boolean(email.trim()) && !isSsoUsername && !isEmailUsername
  const passwordInvalid = showPasswordWarning && password.length > 0 && password.length < 8

  const statusText = apiStatus === "online"
    ? t("API connected")
    : apiStatus === "checking"
      ? t("Checking API connection")
      : t("API unavailable")
  const StatusIcon = apiStatus === "online" || apiStatus === "checking" ? Wifi : WifiOff
  const displayedMessage = currentMessageKey ? t(currentMessageKey, currentMessageParams) : currentMessage

  return (
    <>
      {!showBackground && <div className="fixed inset-0 bg-slate-50 z-0" style={{ pointerEvents: "none" }} />}
      <Card className="w-full max-w-md relative z-10 border-slate-200/80 rounded-3xl py-7 shadow-xl shadow-slate-900/5 sm:py-8">
        <CardHeader className="px-6 sm:px-8">
          <div className="flex items-center justify-between gap-3">
            <h1 className="min-w-0 flex-1">
              <Image
                src="/easyplu-solver-logo.svg"
                alt="EasyPLU solver"
                width={2172}
                height={724}
                priority
                className="h-auto w-full max-w-72"
              />
            </h1>
            <span
              role="status"
              aria-label={statusText}
              title={statusText}
              className={`flex h-10 w-10 shrink-0 items-center justify-center ${apiStatus === "online" ? "text-green-600" : "text-red-600"}`}
            >
              <StatusIcon className={`h-5 w-5 ${apiStatus === "checking" ? "animate-pulse" : ""}`} aria-hidden="true" />
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 px-6 sm:px-8">
          {!showRunPanel && (
          <form onSubmit={handleEasyPLULogin} className="space-y-5">
            <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1" role="group" aria-label={t("Run mode")}>
              {([ ["knowledge", t("Improve knowledge")], ["tasks", t("PLU checks")] ] as const).map(([value, label]) => (
                <button key={value} type="button" disabled={isRunning} aria-pressed={mode === value} onClick={() => setMode(value)}
                  className={`min-h-12 rounded-lg px-2 text-sm font-medium transition-colors ${mode === value ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"}`}>
                  {label}
                </button>
              ))}
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium px-1">
                {t("Global number or email")}
              </Label>
              <Input
                id="email"
                type="text"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                disabled={isRunning}
                placeholder={t("12345678 or name@example.com")}
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setShowUsernameWarning(false)
                }}
                onFocus={() => setShowUsernameWarning(false)}
                onBlur={() => setShowUsernameWarning(true)}
                aria-invalid={usernameInvalid}
                aria-describedby={usernameInvalid ? "username-warning" : undefined}
                required
                className="h-12 rounded-xl border-slate-200 bg-slate-50/70 text-base shadow-none focus-visible:border-blue-500 focus-visible:ring-blue-500/20"
              />
              {usernameInvalid && (
                <p id="username-warning" role="status" className="px-1 text-xs text-amber-700">
                  {t("Enter a valid email or eight-digit global number.")}
                </p>
              )}
            </div>
            <PasswordField password={password} passwordInvalid={passwordInvalid} disabled={isRunning}
              onChange={value => { setPassword(value); setShowPasswordWarning(false) }}
              onFocus={() => setShowPasswordWarning(false)} onBlur={() => setShowPasswordWarning(true)} />

            {mode === "knowledge" && <div className="flex min-h-14 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50/70 px-4">
              <input
                type="checkbox"
                id="customResult"
                checked={showCustomResult}
                onChange={(e) => setShowCustomResult(e.target.checked)}
                disabled={isRunning}
                className="h-5 w-5 shrink-0 rounded border-slate-300 accent-blue-600 cursor-pointer"
              />
              <Label htmlFor="customResult" className="flex min-h-14 flex-1 items-center text-sm font-medium cursor-pointer">
                {t("Custom score")}
              </Label>
            </div>}

            {mode === "knowledge" && showCustomResult && (
              <div className="relative">
                <Input
                  id="targetScore"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{1,2}"
                  maxLength={2}
                  placeholder={t("Score")}
                  value={targetScore ?? ""}
                  onChange={(e) => {
                    const value = e.target.value
                    if (/^[0-9]{0,2}$/.test(value)) {
                      setTargetScore(value ? Number(value) : undefined)
                    }
                  }}
                  className="h-12 rounded-xl border-slate-200 pr-8 text-base"
                  aria-label={t("Custom score as a percentage")}
                  disabled={isRunning}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500">%</span>
              </div>
            )}

            <div className="space-y-3 pt-2">
              <p className="text-xs font-medium text-slate-500">{t("CHOOSE A SIGN-IN METHOD")}</p>
              <div className="grid grid-cols-1 gap-3 min-[380px]:grid-cols-2">
                <Button type="submit" size="lg" className="h-12 rounded-xl bg-blue-600 font-semibold text-white hover:bg-blue-700 cursor-pointer disabled:bg-slate-200 disabled:text-slate-500 disabled:opacity-100" disabled={isRunning || !isEmailUsername || password.length < 8}>
                  easyPLU <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  size="lg"
                  className={`h-12 rounded-xl font-semibold cursor-pointer ${isSsoUsername ? "bg-blue-600 text-white hover:bg-blue-700" : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
                  disabled={isRunning || !isSsoUsername || password.length < 8}
                  onClick={handleSsoLogin}
                >
                  Lidl SSO <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </div>
          </form>
          )}

          {isRunning && !showRunPanel && (
            <div className="space-y-2 text-center">
              <p role="status" className="text-sm text-slate-500">{currentStage === "queued" ? displayedMessage : t("Signing in...")}</p>
              {currentStage === "queued" && <>
                <p className="text-xs tabular-nums text-slate-500">{t("Waiting: {time}", { time: `${Math.floor(queueSeconds / 60)}:${String(queueSeconds % 60).padStart(2, "0")}` })}</p>
                <Button type="button" variant="outline" onClick={cancelQueuedRun}>{t("Cancel request")}</Button>
              </>}
            </div>
          )}

          {isRunning && testStarted && mode === "knowledge" && (
            <p className="text-center text-xs leading-relaxed text-slate-500">
              {t("The test repeats automatically as needed to reach 100% knowledge.")}
            </p>
          )}

          {showRunPanel && <RunProgress mode={mode} taskProgress={taskProgress} currentStage={currentStage}
            submittedItems={submittedItems} currentMessage={displayedMessage} currentKnowledge={currentKnowledge}
            handleSubmitOtp={handleSubmitOtp} otp={otp} setOtp={setOtp} otpSubmitting={otpSubmitting} runId={runId} />}

          {result && <SessionResultCard result={result} onDismiss={() => setResult(null)} />}

          {error && (
            <div role="alert" className="mt-4 p-4 rounded-2xl bg-red-50 border border-red-200">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path fillRule="evenodd" d="M6 18L18 6M6 6l12 12" clipRule="evenodd" />
                </svg>
                <p className="min-w-0 break-words text-sm text-red-700 font-medium">{t("Error:")} {error}</p>
              </div>
            </div>
          )}

          <FooterTools isRunning={isRunning} />
        </CardContent>
      </Card>
    </>
  )
}
