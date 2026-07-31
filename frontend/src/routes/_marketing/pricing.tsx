import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Check } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { featureApi, type PlanPublic } from "@/lib/featureApi"

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

export const Route = createFileRoute("/_marketing/pricing")({
  component: PricingPage,
  head: () => ({
    meta: [{ title: "Pricing - FastAPI Template" }],
  }),
})

function PricingPage() {
  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: featureApi.plans,
  })

  return (
    <div className="mx-auto max-w-6xl px-4 py-20">
      <div className="mb-12 text-center">
        <h1 className="text-3xl font-bold tracking-tight md:text-4xl">
          Pricing
        </h1>
        <p className="mt-2 text-muted-foreground">
          Start free and scale as you grow. No hidden fees.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
        {(plansQuery.data?.data ?? []).map((plan: PlanPublic) => (
          <Card key={plan.id} className="flex flex-col">
            <CardHeader>
              <CardTitle>{plan.name}</CardTitle>
              <CardDescription>{plan.description}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-1 flex-col gap-4">
              <p className="text-4xl font-bold">
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
              <Button className="w-full" asChild>
                <Link to="/signup">Get started</Link>
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  )
}
