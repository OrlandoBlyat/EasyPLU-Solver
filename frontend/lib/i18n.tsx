"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import en from "@/locales/en.json"

declare const require: NodeRequire & {
  context(directory: string, recursive: boolean, pattern: RegExp): {
    keys(): string[]
    (path: string): Catalog | { default: Catalog }
  }
}

// All JSON catalogs in this directory are discovered at build time.
const catalogs = require.context("../locales", false, /^[.\/].*\.json$/)
type Catalog = { name: string; messages: Record<string, string> }
const languages: Record<string, Catalog> = {}
for (const path of catalogs.keys()) {
  const code = path.replace(/^\.\//, "").replace(/\.json$/, "")
  const imported = catalogs(path)
  languages[code] = "default" in imported ? imported.default : imported
}
export const availableLanguages = Object.entries(languages).map(([code, catalog]) => ({ code, name: catalog.name }))
const defaultMessages: Record<string, string> = en.messages
const LanguageContext = createContext({
  locale: "en",
  setLocale: (_locale: string) => {},
  t: (key: string, values?: Record<string, string | number>) => key,
})

export function TranslationProvider({ children, initialLocale, hasLocaleCookie }: {
  children: ReactNode
  initialLocale: string
  hasLocaleCookie: boolean
}) {
  const [locale, updateLocale] = useState(() => languages[initialLocale] ? initialLocale : "en")
  useEffect(() => {
    if (hasLocaleCookie) return
    try {
      const saved = localStorage.getItem("easyplu-language")
      if (saved && languages[saved]) {
        updateLocale(saved)
        document.cookie = `easyplu-language=${encodeURIComponent(saved)}; Path=/; Max-Age=31536000; SameSite=Lax`
      } else if (!saved) {
        const preferred = navigator.languages.find(language => languages[language] || languages[language.split("-")[0]])
        if (preferred) {
          const preferredLocale = languages[preferred] ? preferred : preferred.split("-")[0]
          updateLocale(preferredLocale)
          document.cookie = `easyplu-language=${encodeURIComponent(preferredLocale)}; Path=/; Max-Age=31536000; SameSite=Lax`
        }
      }
    } catch { /* Storage may be unavailable in private browsers. */ }
  }, [hasLocaleCookie])
  useEffect(() => { document.documentElement.lang = locale }, [locale])
  const setLocale = (code: string) => {
    if (!languages[code]) return
    updateLocale(code)
    try { localStorage.setItem("easyplu-language", code) } catch { /* Keep the selection for this session. */ }
    document.cookie = `easyplu-language=${encodeURIComponent(code)}; Path=/; Max-Age=31536000; SameSite=Lax`
  }
  const t = (key: string, values?: Record<string, string | number>) => {
    const message = languages[locale]?.messages[key] || defaultMessages[key] || key
    return message.replace(/\{(\w+)\}/g, (placeholder, name) => values?.[name] === undefined ? placeholder : String(values[name]))
  }
  return <LanguageContext.Provider value={{ locale, setLocale, t }}>{children}</LanguageContext.Provider>
}

export const useTranslation = () => useContext(LanguageContext)
