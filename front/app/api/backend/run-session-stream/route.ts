export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(request: Request) {
  try {
    const baseUrl = process.env.API_BASE_URL || "http://127.0.0.1:8000"
    const upstream = await fetch(`${baseUrl}/run-session-stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Accept-Encoding": "identity",
      },
      body: await request.text(),
      cache: "no-store",
      signal: request.signal,
    })

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") || "text/event-stream",
        "Cache-Control": "no-cache, no-store, no-transform",
        "X-Accel-Buffering": "no",
      },
    })
  } catch {
    return Response.json({ detail: "API ni dosegljiv" }, { status: 502 })
  }
}
