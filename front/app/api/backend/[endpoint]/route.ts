import { readJsonBody, InvalidBody } from "@/lib/request-body"
import { browserSession } from "@/lib/browser-session"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

async function proxy(request: Request, context: { params: Promise<{ endpoint: string }> }) {
  const { endpoint } = await context.params
  if (!(request.method === "GET" && endpoint === "health") &&
      !(request.method === "POST" && endpoint === "submit-otp")) {
    return new Response("Not found", { status: 404 })
  }
  const key = process.env.API_INTERNAL_KEY
  if (!key) return new Response("API access is not configured", { status: 503 })
  try {
    const session = request.method === "POST" ? browserSession(request) : null
    if (request.method === "POST" && !session) {
      return Response.json({ detail: "Prijavna seja ni veljavna." }, { status: 403 })
    }
    const upstream = await fetch(`${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/${endpoint}`, {
      method: request.method,
      headers: { "Content-Type": "application/json", "X-Internal-Key": key,
        ...(session ? { "X-Run-Owner": session.owner } : {}),
        ...(process.env.EDGE_CLIENT_IP_HEADER ? {
          "X-Edge-Client-IP": request.headers.get(process.env.EDGE_CLIENT_IP_HEADER) || "",
        } : {}),
      },
      body: request.method === "POST" ? await readJsonBody(request) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    })
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
        ...(upstream.headers.get("retry-after") ? { "Retry-After": upstream.headers.get("retry-after")! } : {}),
      },
    })
  } catch (error) {
    if (error instanceof InvalidBody) return Response.json({ detail: error.message }, { status: error.status })
    return Response.json({ detail: "API ni dosegljiv" }, { status: 502 })
  }
}

export const GET = proxy
export const POST = proxy
