"use client"

import { useTranslation } from "@/lib/i18n"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"

export function useSchedules() {
  const { t } = useTranslation()
  const [schedule, setSchedule] = useState<{ verified: boolean; enabled: boolean; state?: string | null; next_run?: number | null } | null>(null)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [scheduleConsent, setScheduleConsent] = useState(false)
  const [scheduleBusy, setScheduleBusy] = useState(false)
  const [scheduleError, setScheduleError] = useState<string | null>(null)
  const openSchedule = async () => {
    setScheduleConsent(false)
    setScheduleError(null)
    setSchedule(null)
    setScheduleBusy(true)
    try {
      const response = await fetch("/api/backend/schedule", { cache: "no-store" })
      if (response.status === 403) {
        setSchedule({ verified: false, enabled: false })
      } else {
        if (!response.ok) throw new Error(t("Could not verify your sign-in. Please try again."))
        setSchedule(await response.json())
      }
    } catch (error) {
      setScheduleError(error instanceof Error ? error.message : t("Verification failed."))
    } finally {
      setScheduleBusy(false)
      setScheduleOpen(true)
    }
  }

  const changeSchedule = async (enabled: boolean) => {
    setScheduleBusy(true)
    setScheduleError(null)
    try {
      const response = await fetch("/api/backend/schedule", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, consent: enabled && scheduleConsent }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.detail || t("The change failed."))
      if (!enabled) {
        setScheduleOpen(false)
        setScheduleConsent(false)
      }
      setSchedule(body)
    } catch (error) {
      setScheduleError(error instanceof Error ? error.message : t("The change failed."))
    } finally {
      setScheduleBusy(false)
    }
  }

  return { schedule, scheduleOpen, scheduleConsent, scheduleBusy, scheduleError, setScheduleOpen, setScheduleConsent, openSchedule, changeSchedule }
}

export function ScheduleDialog({ controller, isRunning }: { controller: ReturnType<typeof useSchedules>; isRunning: boolean }) {
  const { t, locale } = useTranslation()
  const { schedule, scheduleOpen, scheduleConsent, scheduleBusy, scheduleError, setScheduleOpen, setScheduleConsent, openSchedule, changeSchedule } = controller
  return (
          <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>{t("Automatic tests")}</DialogTitle>
                <DialogDescription>
                  {schedule?.verified ? (schedule.enabled ? t("Automatic test management is enabled for your account.") : t("Enable automatic test management for your EasyPLU account.")) : t("First complete a test successfully using your EasyPLU email and password, then open this menu within one minute. Lidl SSO is not supported.")}
                </DialogDescription>
              </DialogHeader>
              {schedule?.verified && <>
                {schedule.state === "reauth_required" && <p role="status" className="text-sm text-amber-800">{t("Execution is paused. Enable automatic tests again.")}</p>}
                {schedule.next_run && <p className="text-sm text-slate-600">{t("Next test:")} {new Date(schedule.next_run * 1000).toLocaleString(locale)}</p>}
                {(!schedule.enabled || schedule.state === "reauth_required") && <>
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                    <p className="font-medium">{t("Warning before saving credentials")}</p>
                    <p className="mt-1">{t("We will store your EasyPLU email and password encrypted on the server and run tests regularly on your behalf. An administrator or attacker with server access could obtain these credentials. Disabling automatic tests deletes the saved credentials.")}</p>
                  </div>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" checked={scheduleConsent} onChange={event => setScheduleConsent(event.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-blue-600" />
                    {t("I understand the risk and consent to storing my credentials and running tests automatically.")}
                  </label>
                  <Button type="button" onClick={() => changeSchedule(true)} disabled={!scheduleConsent || scheduleBusy || isRunning}>{t("Save credentials and enable tests")}</Button>
                </>}
                {schedule.enabled && <Button type="button" variant="destructive" className="bg-red-600 text-white hover:bg-red-700" onClick={() => changeSchedule(false)} disabled={scheduleBusy}>{t("Disable automatic tests")}</Button>}
              </>}
              {scheduleError && <p role="alert" className="text-sm text-red-700">{scheduleError}</p>}
            </DialogContent>
          </Dialog>
  )
}
