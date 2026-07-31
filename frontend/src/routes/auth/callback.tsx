import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"

type SearchParams = {
  token?: string
}

const validateSearch = (search: Record<string, unknown>): SearchParams => ({
  token: typeof search.token === "string" ? search.token : undefined,
})

export const Route = createFileRoute("/auth/callback")({
  validateSearch,
  component: OAuthCallback,
})

function OAuthCallback() {
  const navigate = useNavigate()
  const { token } = Route.useSearch()

  useEffect(() => {
    if (token) {
      localStorage.setItem("access_token", token)
      navigate({ to: "/" })
    } else {
      navigate({ to: "/login" })
    }
  }, [token, navigate])

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4">
      <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <p className="text-sm text-muted-foreground">Signing you in…</p>
    </div>
  )
}
