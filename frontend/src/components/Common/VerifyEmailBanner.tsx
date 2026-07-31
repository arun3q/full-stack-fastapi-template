import { useMutation, useQuery } from "@tanstack/react-query"
import { MailWarning } from "lucide-react"

import { Button } from "@/components/ui/button"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi } from "@/lib/featureApi"

export function VerifyEmailBanner() {
  const { user } = useAuth()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const accessQuery = useQuery({
    queryKey: ["userAccess"],
    queryFn: featureApi.userAccess,
    enabled: Boolean(user),
  })

  const resendMutation = useMutation({
    mutationFn: () => featureApi.resendVerificationEmail(user?.email ?? ""),
    onSuccess: () => showSuccessToast("Verification email sent"),
    onError: (error: Error) => showErrorToast(error.message),
  })

  if (!user || accessQuery.data?.is_verified) {
    return null
  }

  return (
    <div className="mb-4 flex items-center justify-between gap-4 rounded-lg border border-amber-300/50 bg-amber-500/10 px-4 py-2.5 text-sm">
      <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
        <MailWarning className="size-4 shrink-0" />
        <span>Please verify your email address to unlock all features.</span>
      </div>
      <Button
        size="sm"
        variant="outline"
        onClick={() => resendMutation.mutate()}
        disabled={resendMutation.isPending}
        data-testid="resend-verification"
      >
        Resend
      </Button>
    </div>
  )
}
