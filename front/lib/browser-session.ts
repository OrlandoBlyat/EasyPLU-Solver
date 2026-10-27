import { createHmac, createHash, randomBytes, timingSafeEqual } from "node:crypto"

const COOKIE = "easyplu_session"

export function browserSession(request: Request, create = false) {
  const key = process.env.API_INTERNAL_KEY
  if (!key) throw new Error("Missing internal key")
  const raw = request.headers.get("cookie")?.split(";").map(item => item.trim())
    .find(item => item.startsWith(`${COOKIE}=`))?.slice(COOKIE.length + 1)
  let id: string | undefined
  if (raw && /^[a-f0-9]{64}\.[a-f0-9]{64}$/.test(raw)) {
    const [candidate, signature] = raw.split(".")
    const expected = createHmac("sha256", key).update(`browser-session:${candidate}`).digest()
    if (timingSafeEqual(expected, Buffer.from(signature, "hex"))) id = candidate
  }
  if (!id && !create) return null
  const fresh = !id
  id ||= randomBytes(32).toString("hex")
  const signature = createHmac("sha256", key).update(`browser-session:${id}`).digest("hex")
  const secure = new URL(request.url).protocol === "https:" ||
    (process.env.NODE_ENV === "production" && process.env.ALLOW_INSECURE_HTTP !== "1")
  return {
    owner: createHash("sha256").update(id).digest("hex"),
    cookie: fresh ? `${COOKIE}=${id}.${signature}; Path=/; HttpOnly; SameSite=Strict${secure ? "; Secure" : ""}` : null,
  }
}
