import { LoginForm } from "@/components/login-form"

export const dynamic = "force-dynamic"

export default async function Home() {
  let initialApiStatus: "online" | "offline" | "error" = "offline"
  try {
    const response = await fetch(`${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/health`, {
      cache: "no-store",
      headers: { "X-Internal-Key": process.env.API_INTERNAL_KEY || "" },
      signal: AbortSignal.timeout(1500),
    })
    initialApiStatus = response.ok ? "online" : "error"
  } catch {
    initialApiStatus = "offline"
  }

  return (
    <main className="flex min-h-svh items-start justify-center px-4 py-8 sm:items-center sm:py-12">
      <LoginForm initialApiStatus={initialApiStatus} />
    </main>
  )
}
