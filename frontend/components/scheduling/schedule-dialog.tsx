"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"

export function useSchedules() {
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
        if (!response.ok) throw new Error("Preverjanje prijave ni uspelo. Poskusite znova.")
        setSchedule(await response.json())
      }
    } catch (error) {
      setScheduleError(error instanceof Error ? error.message : "Preverjanje ni uspelo.")
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
      if (!response.ok) throw new Error(body.detail || "Sprememba ni uspela.")
      if (!enabled) {
        setScheduleOpen(false)
        setScheduleConsent(false)
      }
      setSchedule(body)
    } catch (error) {
      setScheduleError(error instanceof Error ? error.message : "Sprememba ni uspela.")
    } finally {
      setScheduleBusy(false)
    }
  }

  return { schedule, scheduleOpen, scheduleConsent, scheduleBusy, scheduleError, setScheduleOpen, setScheduleConsent, openSchedule, changeSchedule }
}

export function ScheduleDialog({ controller, isRunning }: { controller: ReturnType<typeof useSchedules>; isRunning: boolean }) {
  const { schedule, scheduleOpen, scheduleConsent, scheduleBusy, scheduleError, setScheduleOpen, setScheduleConsent, openSchedule, changeSchedule } = controller
  return (
          <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Samodejni testi</DialogTitle>
                <DialogDescription>
                  {schedule?.verified ? (schedule.enabled ? "Naročeni ste na samodejno upravljanje testov." : "Omogočite samodejno upravljanje testov za svoj račun EasyPLU.") : "Najprej uspešno opravite test z e-pošto in geslom EasyPLU, nato v eni minuti odprite ta meni. Lidl SSO ni podprt."}
                </DialogDescription>
              </DialogHeader>
              {schedule?.verified && <>
                {schedule.state === "reauth_required" && <p role="status" className="text-sm text-amber-800">Izvajanje je ustavljeno. Znova omogočite samodejne teste.</p>}
                {schedule.next_run && <p className="text-sm text-slate-600">Naslednji test: {new Date(schedule.next_run * 1000).toLocaleString("sl-SI")}</p>}
                {(!schedule.enabled || schedule.state === "reauth_required") && <>
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                    <p className="font-medium">Opozorilo pred shranjevanjem prijave</p>
                    <p className="mt-1">Na strežniku bomo šifrirano shranili vašo e-pošto in geslo EasyPLU ter v vašem imenu redno izvajali teste. Skrbnik ali napadalec z dostopom do strežnika lahko pridobi te podatke. Ob odstranitvi iz samodejnih testov izbrišemo shranjeno prijavo.</p>
                  </div>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" checked={scheduleConsent} onChange={event => setScheduleConsent(event.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-blue-600" />
                    Razumem tveganje in soglašam s shranjevanjem prijave ter samodejnim izvajanjem testov.
                  </label>
                  <Button type="button" onClick={() => changeSchedule(true)} disabled={!scheduleConsent || scheduleBusy || isRunning}>Shrani prijavo in omogoči teste</Button>
                </>}
                {schedule.enabled && <Button type="button" variant="destructive" className="bg-red-600 text-white hover:bg-red-700" onClick={() => changeSchedule(false)} disabled={scheduleBusy}>Odstrani me iz samodejnih testov</Button>}
              </>}
              {scheduleError && <p role="alert" className="text-sm text-red-700">{scheduleError}</p>}
            </DialogContent>
          </Dialog>
  )
}
