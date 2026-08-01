import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { Building2, Download, LogOut, ShieldAlert, UserCog } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi } from "@/lib/featureApi"

export const Route = createFileRoute("/_layout/org-settings")({
  component: OrgSettings,
  head: () => ({
    meta: [{ title: "Organization settings - FastAPI Template" }],
  }),
})

function OrgSettings() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { showErrorToast, showSuccessToast } = useCustomToast()

  const orgsQuery = useQuery({
    queryKey: ["organizations"],
    queryFn: featureApi.organizations,
  })
  const activeOrgId = localStorage.getItem("active_org_id")
  const org =
    orgsQuery.data?.data.find((o) => o.id === activeOrgId) ??
    orgsQuery.data?.data[0]

  const membersQuery = useQuery({
    queryKey: ["members", org?.id],
    queryFn: () => featureApi.organizationMembers(org!.id),
    enabled: !!org,
  })

  const suspendMutation = useMutation({
    mutationFn: () => featureApi.suspendOrganization(org!.id),
    onSuccess: () => {
      showSuccessToast("Organization suspended")
      queryClient.invalidateQueries({ queryKey: ["organizations"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const unsuspendMutation = useMutation({
    mutationFn: () => featureApi.unsuspendOrganization(org!.id),
    onSuccess: () => {
      showSuccessToast("Organization re-enabled")
      queryClient.invalidateQueries({ queryKey: ["organizations"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => featureApi.deleteOrganization(org!.id),
    onSuccess: () => {
      localStorage.removeItem("active_org_id")
      showSuccessToast("Organization deleted")
      queryClient.invalidateQueries({ queryKey: ["organizations"] })
      navigate({ to: "/dashboard" })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const exportMutation = useMutation({
    mutationFn: () => featureApi.exportOrganization(org!.id),
    onSuccess: (data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${org?.slug ?? "org"}-export.json`
      a.click()
      URL.revokeObjectURL(url)
      showSuccessToast("Export downloaded")
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const transferMutation = useMutation({
    mutationFn: (userId: string) =>
      featureApi.transferOwnership(org!.id, userId),
    onSuccess: () => {
      showSuccessToast("Ownership transferred")
      queryClient.invalidateQueries({ queryKey: ["members", org?.id] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const leaveMutation = useMutation({
    mutationFn: () => featureApi.leaveOrganization(org!.id),
    onSuccess: () => {
      localStorage.removeItem("active_org_id")
      showSuccessToast("Left organization")
      queryClient.invalidateQueries({ queryKey: ["organizations"] })
      navigate({ to: "/dashboard" })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  if (orgsQuery.isLoading || !org) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Organization settings
        </h1>
        <p className="text-muted-foreground">
          Manage {org.name} — membership, ownership, and data.
        </p>
      </div>

      {!org.is_active ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          This organization is suspended. Members can't access org data until
          it's re-enabled below.
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCog className="size-5" />
            Ownership & membership
          </CardTitle>
          <CardDescription>
            Transfer the owner role to another member
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {(membersQuery.data?.data ?? []).map((member) => (
            <div
              key={member.id}
              className="flex items-center justify-between rounded-md border p-3"
            >
              <div>
                <p className="font-medium">
                  {member.full_name ?? member.email}
                </p>
                <p className="text-sm text-muted-foreground">{member.role}</p>
              </div>
              {member.role !== "owner" && (
                <Button
                  variant="outline"
                  disabled={transferMutation.isPending}
                  onClick={() => {
                    if (window.confirm("Transfer ownership to this member?")) {
                      transferMutation.mutate(member.user_id)
                    }
                  }}
                >
                  Transfer ownership
                </Button>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="size-5" />
            Data portability
          </CardTitle>
          <CardDescription>Export all organization data (GDPR)</CardDescription>
        </CardHeader>
        <CardContent>
          <LoadingButton
            variant="outline"
            loading={exportMutation.isPending}
            onClick={() => exportMutation.mutate()}
          >
            Download export
          </LoadingButton>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <ShieldAlert className="size-5" />
            Danger zone
          </CardTitle>
          <CardDescription>
            Suspend, delete, or leave this organization
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {org.is_active ? (
            <Button
              variant="outline"
              onClick={() => {
                if (
                  window.confirm(
                    "Suspend this organization? Members lose access until it's re-enabled.",
                  )
                ) {
                  suspendMutation.mutate()
                }
              }}
            >
              Suspend
            </Button>
          ) : (
            <LoadingButton
              variant="default"
              disabled={unsuspendMutation.isPending}
              loading={unsuspendMutation.isPending}
              onClick={() => unsuspendMutation.mutate()}
            >
              Re-enable organization
            </LoadingButton>
          )}
          <Button
            variant="outline"
            onClick={() => leaveMutation.mutate()}
            disabled={leaveMutation.isPending}
          >
            <LogOut className="mr-2 size-4" />
            Leave
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              if (
                window.confirm(
                  "Delete this organization permanently? This cannot be undone.",
                )
              ) {
                deleteMutation.mutate()
              }
            }}
          >
            <Building2 className="mr-2 size-4" />
            Delete organization
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
