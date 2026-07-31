import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Building2, Check, CreditCard, Users } from "lucide-react"
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
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi, getActiveOrgId, setActiveOrgId } from "@/lib/featureApi"

export const Route = createFileRoute("/_layout/onboarding")({
  component: Onboarding,
  head: () => ({
    meta: [{ title: "Getting started - FastAPI Template" }],
  }),
})

function Step({
  done,
  index,
  title,
  description,
}: {
  done: boolean
  index: number
  title: string
  description: string
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={`flex size-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold ${
          done
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border text-muted-foreground"
        }`}
      >
        {done ? <Check className="size-4" /> : index}
      </div>
      <div>
        <p className="font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  )
}

function Onboarding() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [orgName, setOrgName] = useState("")

  const orgsQuery = useQuery({
    queryKey: ["organizations"],
    queryFn: featureApi.organizations,
  })
  const subscriptionQuery = useQuery({
    queryKey: ["subscription"],
    queryFn: featureApi.subscription,
  })

  const orgs = orgsQuery.data?.data ?? []
  const personalOnly = orgs.length <= 1
  const activeOrgId = getActiveOrgId() ?? orgs[0]?.id ?? null

  const membersQuery = useQuery({
    queryKey: ["members", activeOrgId],
    queryFn: () => featureApi.organizationMembers(activeOrgId!),
    enabled: Boolean(activeOrgId),
  })
  const hasMembers = (membersQuery.data?.count ?? 0) > 1

  const createOrgMutation = useMutation({
    mutationFn: (name: string) => featureApi.createOrganization(name),
    onSuccess: (org) => {
      setActiveOrgId(org.id)
      showSuccessToast("Organization created")
      queryClient.invalidateQueries()
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const subscription = subscriptionQuery.data
  const hasPlan = Boolean(
    subscription && !["incomplete", "canceled"].includes(subscription.status),
  )

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Getting started</h1>
        <p className="text-muted-foreground">
          Three quick steps to set up your workspace.
        </p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="size-5" />
            Create your organization
          </CardTitle>
          <CardDescription>
            A workspace where your team collaborates.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {personalOnly ? (
            <div className="flex flex-col gap-3 sm:flex-row">
              <Input
                placeholder="Acme Inc"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
              />
              <Button
                onClick={() =>
                  orgName.trim() && createOrgMutation.mutate(orgName.trim())
                }
                disabled={!orgName.trim() || createOrgMutation.isPending}
              >
                Create workspace
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              You're all set — you have an organization.
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="size-5" />
            Invite your team
          </CardTitle>
          <CardDescription>
            Add teammates so they can collaborate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {hasMembers ? (
            <p className="text-sm text-muted-foreground">
              You have teammates in this workspace.
            </p>
          ) : (
            <Button asChild variant="outline">
              <Link to="/members">Invite teammates</Link>
            </Button>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="size-5" />
            Choose a plan
          </CardTitle>
          <CardDescription>
            Pick a plan that fits your team's needs.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          {hasPlan ? (
            <Badge variant="default">
              {subscription?.plan?.name ?? "Subscribed"}
            </Badge>
          ) : (
            <span className="text-sm text-muted-foreground">
              No active plan
            </span>
          )}
          <Button asChild>
            <Link to="/billing">Go to billing</Link>
          </Button>
        </CardContent>
      </Card>

      <div className="mt-8 space-y-4">
        <Step
          index={1}
          done={!personalOnly}
          title="Organization"
          description="Create a workspace for your team."
        />
        <Step
          index={2}
          done={Boolean(hasMembers)}
          title="Team members"
          description="Invite your teammates to join."
        />
        <Step
          index={3}
          done={hasPlan}
          title="Subscription"
          description="Pick a plan that scales with you."
        />
      </div>
    </div>
  )
}
