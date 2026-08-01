import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Mail, Plus, Trash2 } from "lucide-react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import {
  featureApi,
  getActiveOrgId,
  type OrganizationMemberPublic,
} from "@/lib/featureApi"

const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Member",
  viewer: "Viewer",
}

const ROLE_VARIANTS: Record<string, "default" | "secondary" | "outline"> = {
  owner: "default",
  admin: "secondary",
  member: "outline",
  viewer: "outline",
}

export const Route = createFileRoute("/_layout/members")({
  component: MembersPage,
  head: () => ({
    meta: [{ title: "Members - FastAPI Template" }],
  }),
})

function MembersPage() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const [inviteEmail, setInviteEmail] = useState("")
  const [inviteRole, setInviteRole] = useState("member")

  const orgsQuery = useQuery({
    queryKey: ["organizations"],
    queryFn: featureApi.organizations,
  })
  const orgs = orgsQuery.data?.data ?? []
  const orgId =
    getActiveOrgId() ??
    orgs.find((org) => org.id === getActiveOrgId())?.id ??
    orgs[0]?.id ??
    null
  const currentRole = orgs.find((org) => org.id === orgId)?.role ?? ""

  const membersQuery = useQuery({
    queryKey: ["members", orgId],
    queryFn: () => featureApi.organizationMembers(orgId!),
    enabled: Boolean(orgId),
  })

  const invitesQuery = useQuery({
    queryKey: ["invites", orgId],
    queryFn: () => featureApi.organizationInvites(orgId!),
    enabled: Boolean(orgId),
  })

  const inviteMutation = useMutation({
    mutationFn: () => featureApi.inviteMember(orgId!, inviteEmail, inviteRole),
    onSuccess: () => {
      setInviteEmail("")
      showSuccessToast("Invitation sent")
      queryClient.invalidateQueries({ queryKey: ["invites"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const removeMutation = useMutation({
    mutationFn: (userId: string) => featureApi.removeMember(orgId!, userId),
    onSuccess: () => {
      showSuccessToast("Member removed")
      queryClient.invalidateQueries({ queryKey: ["members"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const revokeInviteMutation = useMutation({
    mutationFn: (inviteId: string) => featureApi.revokeInvite(orgId!, inviteId),
    onSuccess: () => {
      showSuccessToast("Invite revoked")
      queryClient.invalidateQueries({ queryKey: ["invites"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const resendInviteMutation = useMutation({
    mutationFn: (inviteId: string) => featureApi.resendInvite(orgId!, inviteId),
    onSuccess: () => showSuccessToast("Invite re-sent"),
    onError: (error: Error) => showErrorToast(error.message),
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      featureApi.changeMemberRole(orgId!, userId, role),
    onSuccess: () => {
      showSuccessToast("Role updated")
      queryClient.invalidateQueries({ queryKey: ["members"] })
    },
    onError: (error: Error) => showErrorToast(error.message),
  })

  const members = membersQuery.data?.data ?? []
  const invites = invitesQuery.data?.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Members</h1>
        <p className="text-muted-foreground">
          Manage who has access to this organization
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-5" />
            Invite a member
          </CardTitle>
          <CardDescription>
            They'll receive an email with a link to join this organization.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row">
          <Input
            type="email"
            placeholder="teammate@example.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            data-testid="invite-email"
          />
          <Select value={inviteRole} onValueChange={setInviteRole}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="member">Member</SelectItem>
              <SelectItem value="admin">Admin</SelectItem>
              <SelectItem value="viewer">Viewer</SelectItem>
            </SelectContent>
          </Select>
          <Button
            onClick={() => inviteMutation.mutate()}
            disabled={!inviteEmail.trim() || inviteMutation.isPending}
          >
            <Mail className="size-4" />
            Send invite
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Members ({members.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member: OrganizationMemberPublic) => (
                <TableRow key={member.id}>
                  <TableCell>
                    <div className="font-medium">
                      {member.full_name || member.email}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {member.email}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge variant={ROLE_VARIANTS[member.role] ?? "outline"}>
                        {ROLE_LABELS[member.role] ?? member.role}
                      </Badge>
                      {currentRole === "owner" && member.role !== "owner" ? (
                        <Select
                          defaultValue={member.role}
                          onValueChange={(role) =>
                            roleMutation.mutate({
                              userId: member.user_id,
                              role,
                            })
                          }
                        >
                          <SelectTrigger className="h-7 w-24 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="member">Member</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="viewer">Viewer</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {currentRole === "owner" && member.role !== "owner" ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Remove member"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Remove ${member.email} from this organization?`,
                            )
                          ) {
                            removeMutation.mutate(member.user_id)
                          }
                        }}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {invites.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Pending invites ({invites.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invites.map((invite) => (
                  <TableRow key={invite.id}>
                    <TableCell>{invite.email}</TableCell>
                    <TableCell>
                      {ROLE_LABELS[invite.role] ?? invite.role}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{invite.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {invite.status === "pending" ? (
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={resendInviteMutation.isPending}
                            onClick={() =>
                              resendInviteMutation.mutate(invite.id)
                            }
                          >
                            Resend
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={revokeInviteMutation.isPending}
                            onClick={() => {
                              if (window.confirm("Revoke this invite?")) {
                                revokeInviteMutation.mutate(invite.id)
                              }
                            }}
                          >
                            Revoke
                          </Button>
                        </div>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
