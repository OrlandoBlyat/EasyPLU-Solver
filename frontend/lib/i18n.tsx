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

export function TranslationProvider({ children }: { children: ReactNode }) {
  const [locale, updateLocale] = useState("en")
  useEffect(() => {
    try {
      const saved = localStorage.getItem("easyplu-language")
      if (saved && languages[saved]) updateLocale(saved)
    } catch { /* Storage may be unavailable in private browsers. */ }
  }, [])
  useEffect(() => { document.documentElement.lang = locale }, [locale])
  const setLocale = (code: string) => {
    if (!languages[code]) return
    updateLocale(code)
    try { localStorage.setItem("easyplu-language", code) } catch { /* Keep the selection for this session. */ }
  }
  const t = (key: string, values?: Record<string, string | number>) => {
    const message = languages[locale]?.messages[key] || defaultMessages[key] || key
    return message.replace(/\{(\w+)\}/g, (placeholder, name) => values?.[name] === undefined ? placeholder : String(values[name]))
  }
  return <LanguageContext.Provider value={{ locale, setLocale, t }}>{children}</LanguageContext.Provider>
}

export const useTranslation = () => useContext(LanguageContext)
