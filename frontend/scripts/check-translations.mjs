import { readFile, readdir } from "node:fs/promises"

const directory = new URL("../locales/", import.meta.url)
const baseline = JSON.parse(await readFile(new URL("en.json", directory), "utf8"))
const placeholders = value => [...value.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort().join(",")
let errors = 0
for (const file of await readdir(directory)) {
  if (!file.endsWith(".json")) continue
  const catalog = JSON.parse(await readFile(new URL(file, directory), "utf8"))
  const code = file.slice(0, -5)
  try { Intl.getCanonicalLocales(code) } catch { throw new Error(`Invalid language tag: ${code}`) }
  if (typeof catalog.name !== "string" || !catalog.name.trim() || !catalog.messages || typeof catalog.messages !== "object" || Array.isArray(catalog.messages)) {
    throw new Error(`${file}: expected a name and messages object`)
  }
  for (const [key, value] of Object.entries(catalog.messages)) {
    if (!(key in baseline.messages) || typeof value !== "string" || (value && placeholders(value) !== placeholders(baseline.messages[key]))) {
      console.error(`${file}: invalid key, value, or placeholders: ${key}`)
      errors++
    }
  }
  const missing = Object.keys(baseline.messages).filter(key => !catalog.messages[key])
  console.log(`${file}: ${Object.keys(baseline.messages).length - missing.length}/${Object.keys(baseline.messages).length} translated`)
}
if (errors) process.exitCode = 1
