import { useQuery } from "@tanstack/react-query"
import { createFileRoute, Link, redirect } from "@tanstack/react-router"
import {
  Bot,
  Check,
  CreditCard,
  KeyRound,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { isLoggedIn } from "@/hooks/useAuth"
import {
  featureApi,
  type PlanPublic,
  type PublicConfig,
} from "@/lib/featureApi"

function formatPrice(amountCents: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountCents / 100)
}

const FEATURES = [
  {
    icon: Users,
    title: "Multi-tenant workspaces",
    description:
      "Organizations, members, roles and invitations — every user gets a personal workspace out of the box.",
  },
  {
    icon: ShieldCheck,
    title: "Role-based access",
    description:
      "Per-tenant roles (owner, admin, member, viewer) with a granular permission registry.",
  },
  {
    icon: CreditCard,
    title: "Subscriptions & billing",
    description:
      "Stripe and Razorpay behind one interface, with plan tiers and quotas.",
  },
  {
    icon: KeyRound,
    title: "Social login & OAuth",
    description:
      "Google, LinkedIn, Meta and GitHub sign-in, plus email/password and verification.",
  },
  {
    icon: Bot,
    title: "AI / LLM streaming",
    description:
      "Token-by-token streaming chat over SSE with OpenAI-compatible and Anthropic providers.",
  },
  {
    icon: Sparkles,
    title: "Background jobs",
    description:
      "Async worker for emails and webhooks powered by ARQ and Redis.",
  },
]

function parseFeatures(raw: string | null): string[] {
  if (!raw) return []
  try {
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

export const Route = createFileRoute("/_marketing/")({
  component: LandingPage,
  beforeLoad: () => {
    if (isLoggedIn()) {
      throw redirect({ to: "/dashboard" })
    }
  },
  head: () => ({
    meta: [{ title: "FastAPI Template - Launch your SaaS fast" }],
  }),
})

function LandingPage() {
  const [config, setConfig] = useState<PublicConfig | null>(null)

  useEffect(() => {
    featureApi
      .publicConfig()
      .then(setConfig)
      .catch(() => setConfig(null))
  }, [])

  const plansQuery = useQuery({
    queryKey: ["plans"],
    queryFn: featureApi.plans,
  })

  const projectName = config?.project_name ?? "FastAPI Template"

  return (
    <div>
      {/* Hero */}
      <section className="border-b">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-24 text-center">
          <span className="rounded-full border bg-muted px-3 py-1 text-xs text-muted-foreground">
            Production-ready full-stack template
          </span>
          <h1 className="max-w-3xl text-4xl font-extrabold tracking-tight md:text-6xl">
            Launch your SaaS on {projectName}
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Multi-tenant workspaces, role-based access, subscriptions, social
            login and AI streaming — batteries included, ready to be your next
            product.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link to="/signup">Get started free</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/pricing">View pricing</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-4 py-20" id="features">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold tracking-tight">
            Everything you need
          </h2>
          <p className="mt-2 text-muted-foreground">
            A complete foundation so you can focus on your product.
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <feature.icon className="size-6 text-primary" />
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="border-t">
        <div className="mx-auto max-w-6xl px-4 py-20">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-bold tracking-tight">
              Simple pricing
            </h2>
            <p className="mt-2 text-muted-foreground">
              Start free and scale as you grow.
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
                  <Button className="w-full" asChild>
                    <Link to="/signup">Get started</Link>
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-20 text-center">
          <h2 className="text-3xl font-bold tracking-tight">
            Ready to build something great?
          </h2>
          <Button size="lg" asChild>
            <Link to="/signup">Create your free account</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}
