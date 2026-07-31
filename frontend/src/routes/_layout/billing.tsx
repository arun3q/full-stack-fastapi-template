import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Check, CreditCard } from "lucide-react"
import { useEffect } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi, type PlanPublic } from "@/lib/featureApi"

type SearchParams = {
  success?: string
  canceled?: string
}

const validateSearch = (search: Record<string, unknown>): SearchParams => ({
  success: typeof search.success === "string" ? search.success : undefined,
  canceled: typeof search.canceled === "string" ? search.canceled : undefined,
})

function formatPrice(amountCents: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountCents / 100)
}

function parseFeatures(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

const STATUS_LABELS: Record<
  string,
  {
    label: string
    variant: "default" | "destructive" | "secondary" | "outline"
  }
> = {
  active: { label: "Active", variant: "default" },
  trialing: { label: "Trialing", variant: "secondary" },
  past_due: { label: "Past due", variant: "destructive" },
  canceled: { label: "Canceled", variant: "outline" },
  incomplete: { label: "Incomplete", variant: "outline" },
}

export const Route = createFileRoute("/_layout/billing")({
  validateSearch,
  component: Billing,
  head: () => ({
    meta: [
      {
        title: "Billing - FastAPI Template",
      },
    ],
  }),
})

function Billing() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { success, canceled } = Route.useSearch()

  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: featureApi.plans,
  })

  const subscriptionQuery = useQuery({
    queryKey: ["subscription"],
    queryFn: featureApi.subscription,
  })

  useEffect(() => {
    if (success) {
      showSuccessToast("Your subscription is being activated")
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    } else if (canceled) {
      showErrorToast("Checkout was canceled")
    }
  }, [success, canceled, queryClient, showSuccessToast, showErrorToast])

  const checkoutMutation = useMutation({
    mutationFn: (planId: string) => featureApi.createCheckout(planId),
    onError: (error: Error) => showErrorToast(error.message),
    onSuccess: (data) => {
      window.location.href = data.url
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => featureApi.cancelSubscription(),
    onSuccess: () => {
      showSuccessToast("Subscription canceled")
      queryClient.invalidateQueries({ queryKey: ["subscription"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const portalMutation = useMutation({
    mutationFn: () => featureApi.billingPortal(),
    onError: (error: Error) => showErrorToast(error.message),
    onSuccess: (data) => {
      window.location.href = data.url
    },
  })

  const subscription = subscriptionQuery.data
  const plans = plansQuery.data?.data ?? []
  const activePlanId = subscription?.plan?.id
  const status = STATUS_LABELS[subscription?.status ?? ""] ?? {
    label: subscription?.status ?? "",
    variant: "outline" as const,
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        <p className="text-muted-foreground">
          Manage your plan and subscription
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="size-5" />
              Current subscription
            </CardTitle>
            <CardDescription>
              Your plan, billing cycle and payment details
            </CardDescription>
          </div>
          {subscription ? (
            <Badge variant={status.variant}>{status.label}</Badge>
          ) : null}
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {subscriptionQuery.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
          ) : subscription ? (
            <>
              <div>
                <p className="text-lg font-semibold">
                  {subscription.plan?.name ?? "Unknown plan"}
                </p>
                <p className="text-muted-foreground">
                  {subscription.provider} ·{" "}
                  {subscription.plan
                    ? formatPrice(
                        subscription.plan.amount_cents,
                        subscription.plan.currency,
                      )
                    : ""}{" "}
                  / {subscription.plan?.billing_interval ?? ""}
                  {subscription.cancel_at_period_end
                    ? " · cancels at period end"
                    : ""}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={() => portalMutation.mutate()}
                  disabled={portalMutation.isPending}
                >
                  Billing portal
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                >
                  Cancel subscription
                </Button>
              </div>
            </>
          ) : (
            <p className="text-muted-foreground">
              You don't have an active subscription yet. Pick a plan below.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {plansQuery.isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 pt-6">
                  <Skeleton className="h-5 w-24" />
                  <Skeleton className="h-8 w-32" />
                  <Skeleton className="h-4 w-full" />
                </CardContent>
              </Card>
            ))
          : plans.map((plan: PlanPublic) => {
              const isCurrent = plan.id === activePlanId
              return (
                <Card key={plan.id} className="flex flex-col">
                  <CardHeader>
                    <CardTitle>{plan.name}</CardTitle>
                    <CardDescription>{plan.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-1 flex-col gap-4">
                    <p className="text-3xl font-bold">
                      {formatPrice(plan.amount_cents, plan.currency)}
                      <span className="text-sm font-normal text-muted-foreground">
                        /{plan.billing_interval}
                      </span>
                    </p>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {parseFeatures(plan.features).map((feature) => (
                        <li key={feature} className="flex items-start gap-2">
                          <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                  <CardFooter>
                    <LoadingButton
                      className="w-full"
                      variant={isCurrent ? "outline" : "default"}
                      disabled={isCurrent}
                      loading={checkoutMutation.isPending}
                      onClick={() => checkoutMutation.mutate(plan.id)}
                    >
                      {isCurrent ? "Current plan" : "Choose plan"}
                    </LoadingButton>
                  </CardFooter>
                </Card>
              )
            })}
      </div>
    </div>
  )
}
