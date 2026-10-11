import { readJsonBody, InvalidBody } from "@/lib/request-body"
import { browserSession } from "@/lib/browser-session"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(request: Request) {
  const key = process.env.API_INTERNAL_KEY
  if (!key) return new Response("API access is not configured", { status: 503 })
  try {
    const session = browserSession(request, true)!
    const baseUrl = process.env.API_BASE_URL || "http://127.0.0.1:8000"
    const upstream = await fetch(`${baseUrl}/run-session-stream`, {
      method: "POST",
      headers: {
        "X-Internal-Key": key,
        "X-Run-Owner": session.owner,
        ...(process.env.EDGE_CLIENT_IP_HEADER ? {
          "X-Edge-Client-IP": request.headers.get(process.env.EDGE_CLIENT_IP_HEADER) || "",
        } : {}),
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Accept-Encoding": "identity",
      },
      body: await readJsonBody(request),
      cache: "no-store",
      signal: request.signal,
    })

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "text/event-stream",
        "Cache-Control": "no-cache, no-store, no-transform",
        "X-Accel-Buffering": "no",
        ...(session.cookie ? { "Set-Cookie": session.cookie } : {}),
        ...(upstream.headers.get("retry-after") ? { "Retry-After": upstream.headers.get("retry-after")! } : {}),
      },
    })
  } catch (error) {
    if (error instanceof InvalidBody) return Response.json({ detail: error.message }, { status: error.status })
    return Response.json({ detail: "API ni dosegljiv" }, { status: 502 })
  }
}
