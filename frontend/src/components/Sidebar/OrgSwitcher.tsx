import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Building2, Check, Plus } from "lucide-react"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi, getActiveOrgId, setActiveOrgId } from "@/lib/featureApi"

const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
}

export function OrgSwitcher() {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const [createMode, setCreateMode] = useState(false)
  const [newName, setNewName] = useState("")

  const orgsQuery = useQuery({
    queryKey: ["organizations"],
    queryFn: featureApi.organizations,
  })

  const orgs = orgsQuery.data?.data ?? []
  const activeOrgId = getActiveOrgId() ?? orgs[0]?.id ?? null
  const activeOrg = orgs.find((org) => org.id === activeOrgId) ?? orgs[0]

  useEffect(() => {
    if (activeOrgId && !orgs.some((org) => org.id === activeOrgId)) {
      setActiveOrgId(null)
    }
  }, [activeOrgId, orgs])

  const switchOrg = (orgId: string) => {
    setActiveOrgId(orgId)
    queryClient.invalidateQueries()
  }

  const createOrgMutation = useMutation({
    mutationFn: (name: string) => featureApi.createOrganization(name),
    onSuccess: (org) => {
      setCreateMode(false)
      setNewName("")
      switchOrg(org.id)
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  return (
    <SidebarMenuItem>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <SidebarMenuButton tooltip="Organization">
            <Building2 className="size-4 text-muted-foreground" />
            <span className="truncate">
              {activeOrg?.name ?? "Organization"}
            </span>
            {activeOrg?.role ? (
              <span className="ml-auto rounded-full border px-2 py-0.5 text-[10px] text-muted-foreground">
                {ROLE_LABELS[activeOrg.role] ?? activeOrg.role}
              </span>
            ) : null}
          </SidebarMenuButton>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="right" align="start" className="w-64">
          <DropdownMenuLabel>Organizations</DropdownMenuLabel>
          {orgs.map((org) => (
            <DropdownMenuItem
              key={org.id}
              onClick={() => switchOrg(org.id)}
              data-testid={`org-${org.slug}`}
            >
              <Building2 className="size-4" />
              <span className="flex-1 truncate">{org.name}</span>
              {org.id === activeOrgId ? <Check className="size-4" /> : null}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          {createMode ? (
            <div className="flex items-center gap-2 px-2 py-1.5">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newName.trim()) {
                    createOrgMutation.mutate(newName.trim())
                  }
                  if (e.key === "Escape") setCreateMode(false)
                }}
                placeholder="Organization name"
                className="h-8 flex-1 rounded-md border bg-transparent px-2 text-sm outline-none"
              />
              <Button
                size="sm"
                onClick={() =>
                  newName.trim() && createOrgMutation.mutate(newName.trim())
                }
              >
                Create
              </Button>
            </div>
          ) : (
            <DropdownMenuItem onClick={() => setCreateMode(true)}>
              <Plus className="size-4" />
              New organization
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </SidebarMenuItem>
  )
}
