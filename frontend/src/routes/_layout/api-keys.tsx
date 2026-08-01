import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { KeyRound, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
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

export const Route = createFileRoute("/_layout/api-keys")({
  component: ApiKeys,
  head: () => ({
    meta: [{ title: "API keys - FastAPI Template" }],
  }),
})

function ApiKeys() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [name, setName] = useState("")
  const [scopes, setScopes] = useState("read,write")
  const [created, setCreated] = useState<string | null>(null)

  const keysQuery = useQuery({
    queryKey: ["api-keys"],
    queryFn: featureApi.apiKeys,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      featureApi.createApiKey(
        name,
        scopes.split(",").map((s) => s.trim()),
      ),
    onSuccess: (data) => {
      setCreated(data.key)
      setShowCopy(true)
      setName("")
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (keyId: string) => featureApi.revokeApiKey(keyId),
    onSuccess: () => {
      showSuccessToast("API key revoked")
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const [showCopy, setShowCopy] = useState(false)

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">API keys</h1>
        <p className="text-muted-foreground">
          Service accounts for machine access (SCIM requires the scim scope).
        </p>
      </div>

      {showCopy && created ? (
        <Card>
          <CardContent className="pt-6">
            <p className="mb-2 font-medium text-emerald-600">
              Copy this key now — it won't be shown again.
            </p>
            <code className="block break-all rounded-md bg-muted p-3 text-sm">
              {created}
            </code>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5" />
            New key
          </CardTitle>
          <CardDescription>Name and comma-separated scopes</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input
            placeholder="Key name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            data-testid="api-key-name"
          />
          <Input
            placeholder="scopes"
            value={scopes}
            onChange={(e) => setScopes(e.target.value)}
            className="w-48"
          />
          <LoadingButton
            onClick={() => createMutation.mutate()}
            disabled={!name.trim() || createMutation.isPending}
            loading={createMutation.isPending}
          >
            <Plus className="mr-2 size-4" />
            Create
          </LoadingButton>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Existing keys</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {keysQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (keysQuery.data?.data ?? []).length === 0 ? (
            <p className="text-muted-foreground">No API keys yet.</p>
          ) : (
            (keysQuery.data?.data ?? []).map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div>
                  <p className="font-medium">{key.name}</p>
                  <div className="flex flex-wrap gap-1">
                    {key.scopes.map((scope) => (
                      <Badge key={scope} variant="secondary">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Revoke ${key.name}`}
                  onClick={() => {
                    if (window.confirm(`Revoke ${key.name}?`)) {
                      revokeMutation.mutate(key.id)
                    }
                  }}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
