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

export const Route = createFileRoute("/verify-email")({
  validateSearch,
  component: VerifyEmailPage,
  beforeLoad: () => {
    if (!isLoggedIn()) {
      throw redirect({ to: "/login" })
    }
  },
})

function VerifyEmailPage() {
  const navigate = useNavigate()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { token } = Route.useSearch()

  const verifyMutation = useMutation({
    mutationFn: (verifyToken: string) => featureApi.verifyEmail(verifyToken),
    onSuccess: (data) => {
      showSuccessToast(data.message)
      navigate({ to: "/dashboard" })
    },
    onError: (error: Error) => {
      showErrorToast(error.message)
      navigate({ to: "/dashboard" })
    },
  })

  useEffect(() => {
    if (token) verifyMutation.mutate(token)
    else navigate({ to: "/dashboard" })
  }, [token, verifyMutation.mutate, navigate])

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4">
      <div className="size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      <p className="text-sm text-muted-foreground">Verifying your email…</p>
    </div>
  )
}
