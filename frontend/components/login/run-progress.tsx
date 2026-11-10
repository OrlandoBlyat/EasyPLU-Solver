"use client"

import { useTranslation } from "@/lib/i18n"
import type { FormEvent } from "react"
import { Progress } from "@/components/ui/progress"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface RunProgressProps {
  mode: "knowledge" | "tasks"
  taskProgress: { completed: number; total: number } | null
  currentStage: string
  submittedItems: { current: number; total: number } | null
  currentMessage: string
  currentKnowledge: number | null
  handleSubmitOtp: (event: FormEvent) => Promise<void>
  otp: string
  setOtp: (value: string) => void
  otpSubmitting: boolean
  runId: string | null
}

export function RunProgress({ mode, taskProgress, currentStage, submittedItems, currentMessage, currentKnowledge, handleSubmitOtp, otp, setOtp, otpSubmitting, runId }: RunProgressProps) {
  const { t } = useTranslation()
  const getStageLabel = (stage: string): string => {
    const stageLabels: Record<string, string> = {
      initializing: t("Initializing"),
      logging_in: t("Signing in"),
      checking_tasks: t("Checking tasks"),
      assigned_tasks: t("PLU checks"),
      otp_required: t("SMS code"),
      creating_session: t("Creating session"),
      starting_execution: t("Starting execution"),
      fetching_items: t("Fetching items"),
      submitting_answers: t("Submitting answers"),
      submitting_result: t("Submitting score"),
      completed: t("Completed"),
      error: t("Error"),
      attempt_start: t("Preparing test"),
      attempt_complete: t("Checking knowledge"),
      retrying: t("Continuing test"),
    }
    return stageLabels[stage] || stage
  }

  const isSubmittingAnswers = currentStage === "submitting_answers"
  return (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-blue-100 bg-blue-50/50 p-4 space-y-4">
              <div className="w-full space-y-3" role="status" aria-live="polite">
                {mode === "tasks" && taskProgress && (
                  <div className="space-y-2 border-b border-blue-100 pb-4">
                    <div className="flex items-center justify-between gap-3 text-sm font-medium text-slate-700">
                      <span>{t("PLU checks")}</span>
                      <span className="tabular-nums">{taskProgress.completed} / {taskProgress.total}</span>
                    </div>
                    <Progress aria-label={t("PLU checks progress")} value={taskProgress.total ? taskProgress.completed / taskProgress.total * 100 : 100} className="h-2 [&>div]:bg-blue-600" />
                  </div>
                )}
                {/* Stage indicator */}
                {isSubmittingAnswers ? (
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="font-medium text-slate-700">{t("Submitting answers")}</span>
                    {submittedItems && (
                      <span className="shrink-0 tabular-nums text-slate-500">
                        {submittedItems.current} / {submittedItems.total}
                      </span>
                    )}
                  </div>
                ) : currentStage && (
                  <div className="text-center">
                    <p className="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1">
                      {getStageLabel(currentStage)}
                    </p>
                    {currentMessage && (
                      <p className="text-xs text-gray-600 dark:text-gray-400">{currentMessage}</p>
                    )}
                    {/* Knowledge info */}
                    {mode === "knowledge" && currentKnowledge !== null && (
                      <div className="flex items-center justify-center gap-3 mt-2">
                        {currentKnowledge !== null && (
                          <span className="text-xs font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/30 px-2 py-1 rounded">
                            {t("Knowledge:")} {currentKnowledge.toFixed(2)}%
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Progress bar */}
                {isSubmittingAnswers && (
                <div className="w-full space-y-2">
                  <Progress value={submittedItems && submittedItems.total > 0 ? (submittedItems.current / submittedItems.total) * 100 : 0} className="h-2 [&>div]:bg-blue-600" />
                </div>
                )}

                {currentStage === "otp_required" && (
                  <form onSubmit={handleSubmitOtp} className="space-y-3 pt-2">
                    <Input
                      id="otp"
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]{6}"
                      minLength={6}
                      maxLength={6}
                      autoComplete="one-time-code"
                      aria-label={t("SMS code")}
                      placeholder={t("SMS code")}
                      value={otp}
                      onChange={(e) => setOtp(e.target.value)}
                      className="h-12 rounded-xl border-slate-200 bg-slate-50/70 text-base shadow-none focus-visible:border-blue-500 focus-visible:ring-blue-500/20"
                      required
                    />
                    <Button type="submit" className="h-12 w-full rounded-xl bg-blue-600 hover:bg-blue-700" disabled={otpSubmitting || !runId || !/^[0-9]{6}$/.test(otp)}>
                      {otpSubmitting ? t("Sending...") : t("Send SMS code")}
                    </Button>
                  </form>
                )}

                {/* Loading spinner */}
                {isSubmittingAnswers && (
                <div className="w-full pt-1">
                  <div className="relative mx-auto h-6 w-6">
                    <div className="absolute inset-0 rounded-full border-2 border-gray-200 dark:border-gray-700"></div>
                    <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-600 border-r-blue-500 animate-spin"></div>
                  </div>
                </div>
                )}
              </div>
            </div>

  )
}
