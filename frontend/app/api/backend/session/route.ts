import { browserSession } from "@/lib/server/browser-session"

export const runtime = "nodejs"

// Establish the owner cookie before opening a long-lived SSE response. Browsers
// are not required to make a Set-Cookie on an unfinished stream available to a
// concurrent SMS-code request.
export async function POST(request: Request) {
  try {
    const session = browserSession(request, true)!
    return Response.json(
      { status: "ok" },
      { headers: session.cookie ? { "Set-Cookie": session.cookie } : {} },
    )
  } catch {
    return Response.json({ detail: "Could not create a login session." }, { status: 503 })
  }
}
