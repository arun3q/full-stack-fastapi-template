import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"

import { storeTokens } from "@/lib/featureApi"

type SearchParams = {
  token?: string
  refresh?: string
}

const validateSearch = (search: Record<string, unknown>): SearchParams => ({
  token: typeof search.token === "string" ? search.token : undefined,
  refresh: typeof search.refresh === "string" ? search.refresh : undefined,
})

export const Route = createFileRoute("/auth/callback")({
  validateSearch,
  component: OAuthCallback,
})

function OAuthCallback() {
  const navigate = useNavigate()
  const { token, refresh } = Route.useSearch()

  useEffect(() => {
    if (token) {
      storeTokens(token, refresh)
      navigate({ to: "/dashboard" })
    } else {
      navigate({ to: "/login" })
    }
  }, [token, refresh, navigate])

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4">
      <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <p className="text-sm text-muted-foreground">Signing you in…</p>
    </div>
  )
}
