import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { KeyRound, MonitorSmartphone } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi } from "@/lib/featureApi"

export const Route = createFileRoute("/_layout/security")({
  component: Security,
  head: () => ({
    meta: [{ title: "Security - FastAPI Template" }],
  }),
})

function Security() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [code, setCode] = useState("")
  const [password, setPassword] = useState("")
  const [setupData, setSetupData] = useState<{ otpauth_url: string } | null>(
    null,
  )

  const sessionsQuery = useQuery({
    queryKey: ["sessions"],
    queryFn: featureApi.sessions,
  })

  const totpSetupMutation = useMutation({
    mutationFn: (pw: string) => featureApi.totpSetup(pw),
    onSuccess: (data) => setSetupData(data),
    onError: (error: Error) => showErrorToast(error.message),
  })

  const totpEnableMutation = useMutation({
    mutationFn: () => featureApi.totpEnable(code, password),
    onSuccess: () => {
      showSuccessToast("Two-factor authentication enabled")
      setSetupData(null)
      setCode("")
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const totpDisableMutation = useMutation({
    mutationFn: () => featureApi.totpDisable(code),
    onSuccess: () => {
      showSuccessToast("Two-factor authentication disabled")
      setCode("")
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (sessionId: string) => featureApi.revokeSession(sessionId),
    onSuccess: () => {
      showSuccessToast("Session revoked")
      queryClient.invalidateQueries({ queryKey: ["sessions"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Security</h1>
        <p className="text-muted-foreground">
          Two-factor authentication and active sessions.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5" />
            Two-factor authentication
          </CardTitle>
          <CardDescription>
            Authenticator-app TOTP codes on login
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {setupData ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Scan this code in your authenticator app, then enter a code:
              </p>
              <code className="break-all rounded-md bg-muted p-3 text-xs">
                {setupData.otpauth_url}
              </code>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-40"
                />
                <Input
                  placeholder="6-digit code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  data-testid="totp-code"
                />
                <LoadingButton
                  onClick={() => totpEnableMutation.mutate()}
                  disabled={code.length < 6 || totpEnableMutation.isPending}
                  loading={totpEnableMutation.isPending}
                >
                  Enable
                </LoadingButton>
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <LoadingButton
                variant="outline"
                onClick={() => totpSetupMutation.mutate(password)}
                disabled={!password}
                loading={totpSetupMutation.isPending}
              >
                Set up 2FA
              </LoadingButton>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-40"
                />
                <Input
                  placeholder="Code to disable"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="w-40"
                />
                <Button
                  variant="destructive"
                  onClick={() => totpDisableMutation.mutate()}
                  disabled={code.length < 6 || !password}
                >
                  Disable
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MonitorSmartphone className="size-5" />
            Active sessions
          </CardTitle>
          <CardDescription>Revoke devices you don't recognize</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {sessionsQuery.isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (sessionsQuery.data?.data ?? []).length === 0 ? (
            <p className="text-muted-foreground">No active sessions.</p>
          ) : (
            (sessionsQuery.data?.data ?? []).map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div>
                  <p className="font-medium">
                    {session.user_agent ?? "Unknown device"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {session.ip_address ?? "Unknown IP"}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (window.confirm("Revoke this session?")) {
                      revokeMutation.mutate(session.id)
                    }
                  }}
                >
                  Revoke
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
