import { useMutation } from "@tanstack/react-query"
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router"
import { useEffect } from "react"

import { isLoggedIn } from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi } from "@/lib/featureApi"

type SearchParams = {
  token?: string
}

const validateSearch = (search: Record<string, unknown>): SearchParams => ({
  token: typeof search.token === "string" ? search.token : undefined,
})

export const Route = createFileRoute("/invite")({
  validateSearch,
  component: InvitePage,
  beforeLoad: () => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login" })
    }
  },
})

function InvitePage() {
  const navigate = useNavigate()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { token } = Route.useSearch()

  const acceptMutation = useMutation({
    mutationFn: (inviteToken: string) => featureApi.acceptInvite(inviteToken),
    onSuccess: () => {
      showSuccessToast("Invitation accepted")
      navigate({ to: "/dashboard" })
    },
    onError: (error: Error) => {
      showErrorToast(error.message)
      navigate({ to: "/dashboard" })
    },
  })

  useEffect(() => {
    if (token) acceptMutation.mutate(token)
    else navigate({ to: "/dashboard" })
  }, [token, navigate, acceptMutation.mutate])

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4">
      <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <p className="text-sm text-muted-foreground">Accepting invitation…</p>
    </div>
  )
}
