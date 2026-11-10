"use client"

import { useTranslation } from "@/lib/i18n"
import { useEffect, useState } from "react"
import { ArrowBigUpDash, Eye, EyeOff } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface PasswordFieldProps {
  password: string
  passwordInvalid: boolean
  disabled: boolean
  onChange: (value: string) => void
  onFocus: () => void
  onBlur: () => void
}

export function PasswordField({ password, passwordInvalid, disabled, onChange, onFocus, onBlur }: PasswordFieldProps) {
  const { t } = useTranslation()
  const [showPassword, setShowPassword] = useState(false)
  const [capsLock, setCapsLock] = useState(false)

  useEffect(() => {
    if (!password) setShowPassword(false)
  }, [password])

  useEffect(() => {
    // Track the modifier outside the field too; moving focus must not clear it.
    const updateCapsLock = (event: KeyboardEvent) => {
      if (event.key === "CapsLock") {
        if (!event.repeat) setCapsLock(previous => !previous)
        return
      }
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return
      const isLetter = event.key.length === 1 && event.key.toLowerCase() !== event.key.toUpperCase()
      if (isLetter) {
        // Some browser/keyboard combinations report the modifier incorrectly.
        const uppercase = event.key === event.key.toUpperCase()
        setCapsLock(event.getModifierState("CapsLock") || uppercase !== event.shiftKey)
      } else if (event.getModifierState("CapsLock")) {
        setCapsLock(true)
      }
    }
    const resetCapsLock = () => setCapsLock(false)
    window.addEventListener("keydown", updateCapsLock, true)
    window.addEventListener("blur", resetCapsLock)
    return () => {
      window.removeEventListener("keydown", updateCapsLock, true)
      window.removeEventListener("blur", resetCapsLock)
    }
  }, [])

  const visibilityLabel = showPassword ? t("Hide password") : t("Show password")

  return (
    <div className="space-y-2">
      <Label htmlFor="password" className="text-sm font-medium px-1">{t("Password")}</Label>
      <div className="relative">
        <Input
          id="password"
          type={showPassword ? "text" : "password"}
          placeholder="••••••••"
          value={password}
          onChange={event => onChange(event.target.value)}
          onFocus={onFocus}
          onMouseDown={event => { if (event.getModifierState("CapsLock")) setCapsLock(true) }}
          onBlur={onBlur}
          minLength={8}
          aria-invalid={passwordInvalid}
          aria-describedby={[passwordInvalid && "password-warning", capsLock && "caps-lock-warning"].filter(Boolean).join(" ") || undefined}
          required
          className="h-12 rounded-xl border-slate-200 bg-slate-50/70 pr-12 text-base shadow-none focus-visible:border-blue-500 focus-visible:ring-blue-500/20"
          autoComplete="current-password"
          disabled={disabled}
        />
        <button
          type="button"
          onClick={() => setShowPassword(previous => !previous)}
          disabled={disabled}
          className={`absolute right-0 top-0 flex h-12 w-12 items-center justify-center rounded-xl focus-visible:outline-2 focus-visible:outline-blue-600 transition-colors disabled:opacity-50 ${capsLock ? "text-red-600 hover:text-red-700" : "text-slate-500 hover:text-slate-900"}`}
          aria-label={capsLock ? `${visibilityLabel}. ${t("Caps Lock is on.")}` : visibilityLabel}
          title={capsLock ? t("Caps Lock is on") : visibilityLabel}
          aria-pressed={showPassword}
        >
          {capsLock ? <span className="flex h-7 w-7 items-center justify-center rounded-md bg-red-50 ring-1 ring-red-200"><ArrowBigUpDash className="h-5 w-5" strokeWidth={2.5} aria-hidden="true" /></span> : showPassword ? <EyeOff className="h-5 w-5" aria-hidden="true" /> : <Eye className="h-5 w-5" aria-hidden="true" />}
        </button>
      </div>
      <span id="caps-lock-warning" role="status" className="sr-only">{capsLock ? t("Caps Lock is on.") : ""}</span>
      {passwordInvalid && (
        <p id="password-warning" role="status" className="px-1 text-xs text-amber-700">{t("Password must contain at least 8 characters.")}</p>
      )}
    </div>
  )
}
