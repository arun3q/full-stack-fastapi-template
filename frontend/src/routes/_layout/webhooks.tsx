import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Plus, Trash2, Webhook } from "lucide-react"
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

export const Route = createFileRoute("/_layout/webhooks")({
  component: Webhooks,
  head: () => ({
    meta: [{ title: "Webhooks - FastAPI Template" }],
  }),
})

function Webhooks() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [url, setUrl] = useState("")
  const [events, setEvents] = useState("*")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const webhooksQuery = useQuery({
    queryKey: ["webhooks"],
    queryFn: featureApi.webhooks,
  })

  const deliveriesQuery = useQuery({
    queryKey: ["webhook-deliveries", selectedId],
    queryFn: () => featureApi.webhookDeliveries(selectedId!),
    enabled: !!selectedId,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      featureApi.createWebhook(
        url,
        events.split(",").map((e) => e.trim()),
      ),
    onSuccess: () => {
      showSuccessToast("Webhook created")
      setUrl("")
      queryClient.invalidateQueries({ queryKey: ["webhooks"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (webhookId: string) => featureApi.deleteWebhook(webhookId),
    onSuccess: () => {
      showSuccessToast("Webhook deleted")
      queryClient.invalidateQueries({ queryKey: ["webhooks"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Webhooks</h1>
        <p className="text-muted-foreground">
          Outbound signed events delivered to your endpoint (HMAC signature).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Webhook className="size-5" />
            New endpoint
          </CardTitle>
          <CardDescription>
            HTTPS URL and comma-separated events (e.g. * or item.created)
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input
            placeholder="https://example.com/hooks"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            data-testid="webhook-url"
          />
          <Input
            placeholder="events"
            value={events}
            onChange={(e) => setEvents(e.target.value)}
            className="w-48"
          />
          <LoadingButton
            onClick={() => createMutation.mutate()}
            disabled={!url.trim() || createMutation.isPending}
            loading={createMutation.isPending}
          >
            <Plus className="mr-2 size-4" />
            Create
          </LoadingButton>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Endpoints</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {webhooksQuery.isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : (webhooksQuery.data?.data ?? []).length === 0 ? (
            <p className="text-muted-foreground">No webhooks configured.</p>
          ) : (
            (webhooksQuery.data?.data ?? []).map((webhook) => (
              <div
                key={webhook.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div>
                  <p className="break-all font-medium">{webhook.url}</p>
                  <div className="flex flex-wrap gap-1">
                    {webhook.events.map((event) => (
                      <Badge key={event} variant="secondary">
                        {event}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setSelectedId(
                        selectedId === webhook.id ? null : webhook.id,
                      )
                    }
                  >
                    Deliveries
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Delete webhook"
                    onClick={() => {
                      if (window.confirm("Delete this webhook?")) {
                        deleteMutation.mutate(webhook.id)
                      }
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      {selectedId ? (
        <Card>
          <CardHeader>
            <CardTitle>Recent deliveries</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {deliveriesQuery.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (deliveriesQuery.data?.data ?? []).length === 0 ? (
              <p className="text-muted-foreground">No deliveries yet.</p>
            ) : (
              (deliveriesQuery.data?.data ?? []).map((delivery) => (
                <div
                  key={delivery.id}
                  className="flex items-center justify-between rounded-md border p-2 text-sm"
                >
                  <span>{delivery.event}</span>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        delivery.status === "success" ? "default" : "secondary"
                      }
                    >
                      {delivery.status}
                    </Badge>
                    <span className="text-muted-foreground">
                      {delivery.attempts} attempt(s)
                    </span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
