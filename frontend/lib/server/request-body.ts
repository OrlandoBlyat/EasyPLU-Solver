const MAX_BODY_BYTES = 8192

export class InvalidBody extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function readJsonBody(request: Request): Promise<string> {
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    throw new InvalidBody(415, "Zahteva mora biti JSON.")
  }
  const declared = request.headers.get("content-length")
  if (declared && (!/^\d+$/.test(declared) || Number(declared) > MAX_BODY_BYTES)) {
    throw new InvalidBody(413, "Zahteva je prevelika.")
  }
  if (!request.body) throw new InvalidBody(400, "Manjkajo podatki zahteve.")
  const reader = request.body.getReader()
  const chunks: Uint8Array[] = []
  let size = 0
  const deadline = Date.now() + 10000
  try {
    while (true) {
      let timeout: ReturnType<typeof setTimeout> | undefined
      const result = await Promise.race([
        reader.read(),
        new Promise<never>((_, reject) => {
          timeout = setTimeout(() => reject(new InvalidBody(408, "Čas pošiljanja je potekel.")), Math.max(0, deadline - Date.now()))
        }),
      ]).finally(() => clearTimeout(timeout))
      if (result.done) break
      size += result.value.byteLength
      if (size > MAX_BODY_BYTES) throw new InvalidBody(413, "Zahteva je prevelika.")
      chunks.push(result.value)
    }
  } catch (error) {
    void reader.cancel().catch(() => {})
    throw error
  } finally {
    reader.releaseLock()
  }
  const body = new Uint8Array(size)
  let offset = 0
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength }
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(body)
    const parsed = JSON.parse(text)
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error()
    return text
  } catch {
    throw new InvalidBody(400, "Neveljavni podatki zahteve.")
  }
}
