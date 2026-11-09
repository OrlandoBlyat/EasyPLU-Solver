"use client"

import { useState } from "react"
import { Download, Code2, Wrench, Loader2, CalendarClock } from "lucide-react"
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { ScheduleDialog, useSchedules } from "@/components/scheduling/schedule-dialog"

const footerIconClass = "inline-flex h-11 w-11 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-60"

export function FooterTools({ isRunning }: { isRunning: boolean }) {
  const controller = useSchedules()
  const { scheduleBusy, openSchedule } = controller
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const downloadCatalog = async () => {
    setIsExporting(true)
    setExportError(null)
    try {
      const response = await fetch("/api/backend/catalog-pdf", { cache: "no-store" })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail || "Prenos PDF ni uspel. Poskusite znova.")
      }
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement("a")
      link.href = url
      link.download = "plu-catalog.pdf"
      document.body.appendChild(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "Prenos PDF ni uspel.")
    } finally {
      setIsExporting(false)
    }
  }

  return <>
    <ScheduleDialog controller={controller} isRunning={isRunning} />
          <div className="flex flex-col items-center gap-2 pt-4 border-t border-gray-100">
            <div className="flex flex-wrap items-center justify-center gap-3">
            <a
              href="https://github.com/OrlandoBlyat/EasyPLU-Solver"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Projekt na GitHubu"
              title="GitHub"
              className={footerIconClass}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.387.6.112.82-.262.82-.583 0-.288-.01-1.05-.015-2.06-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.09-.746.083-.73.083-.73 1.205.084 1.84 1.238 1.84 1.238 1.07 1.834 2.807 1.304 3.492.997.108-.776.418-1.304.762-1.604-2.665-.304-5.466-1.332-5.466-5.933 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.3 1.23a11.5 11.5 0 013.003-.404c1.018.004 2.045.137 3.003.404 2.29-1.552 3.296-1.23 3.296-1.23.655 1.653.243 2.873.12 3.176.77.84 1.233 1.91 1.233 3.22 0 4.61-2.807 5.625-5.478 5.922.43.372.823 1.102.823 2.222 0 .324.218.7.825.582C20.565 21.796 24 17.297 24 12c0-6.63-5.37-12-12-12z"
                  clipRule="evenodd"
                />
              </svg>
            </a>
            <a href="https://github.com/OrlandoBlyat/EasyPLU-Solver" target="_blank" rel="noopener noreferrer"
              aria-label="Open source" title="Open source" className={footerIconClass}>
              <Code2 className="h-5 w-5" aria-hidden="true" />
            </a>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" disabled={isExporting} aria-busy={isExporting}
                  aria-label={isExporting ? "Pripravljanje PDF..." : "Orodja"}
                  title={isExporting ? "Pripravljanje PDF..." : "Orodja"}
                  className={footerIconClass}>
                  {isExporting ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> : <Wrench className="h-5 w-5" aria-hidden="true" />}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top">
                <DropdownMenuItem onSelect={() => void downloadCatalog()} disabled={isRunning || isExporting}>
                  <Download aria-hidden="true" />
                  Prenesi katalog PLU (PDF)
                </DropdownMenuItem>
                <DropdownMenuItem disabled={scheduleBusy || isRunning} onSelect={() => void openSchedule()}>
                  <CalendarClock aria-hidden="true" />
                  Samodejni testi
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            </div>
            {exportError && <p role="alert" className="text-sm text-red-700">{exportError}</p>}
            <p className="text-xs text-gray-500 text-center">© 2026 Orlando Dlugoš Čeh</p>
          </div>
  </>
}
