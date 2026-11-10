"use client"

import { useTranslation } from "@/lib/i18n"
import { X } from "lucide-react"
import type { SessionResult } from "@/lib/client/session-types"

export function SessionResultCard({ result, onDismiss }: { result: SessionResult; onDismiss: () => void }) {
  const { t } = useTranslation()
  return (
            <div className="mt-4 p-4 rounded-2xl bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30 border border-green-200 dark:border-green-800 space-y-2 relative">
              <button
                onClick={onDismiss}
                className="absolute top-1 right-1 flex h-11 w-11 items-center justify-center rounded-full hover:bg-green-100 dark:hover:bg-green-900/50 transition-colors touch-manipulation"
                aria-label={t("Dismiss results")}
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
                  {result.tasks_only ? t("PLU checks completed") : t("Test completed successfully")}
                </h3>
              </div>

              {result.tasks_only ? (
                <p className="py-2 text-sm text-green-800">{result.assigned_tasks_completed ? t("Completed checks: {count}", { count: result.assigned_tasks_completed }) : t("No PLU checks assigned.")}</p>
              ) : <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-green-100 bg-white/60 p-3 dark:border-green-800 dark:bg-white/5">
                  <p className="mb-1 text-xs text-gray-600 dark:text-gray-400">{t("Ranking (in store)")}</p>
                  <p className="text-xl font-bold text-green-700 dark:text-green-400">#{result.user_ranking_in_store}</p>
                </div>
                <div className="rounded-xl border border-green-100 bg-white/60 p-3 dark:border-green-800 dark:bg-white/5">
                  <p className="mb-1 text-xs text-gray-600 dark:text-gray-400">{t("Knowledge")}</p>
                  <p className="text-xl font-bold text-green-700 dark:text-green-400">{result.user_knowledge.toFixed(1)}%</p>
                </div>
              </div>}
            </div>

  )
}
