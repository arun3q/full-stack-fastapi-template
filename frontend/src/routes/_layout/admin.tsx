import { useQuery, useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import { featureApi } from "@/lib/featureApi"

function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/dashboard",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Admin - FastAPI Template",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function OverviewTab() {
  const { data } = useQuery({
    queryKey: ["admin-overview"],
    queryFn: featureApi.adminOverview,
  })

  const stats = data ?? {
    users: 0,
    organizations: 0,
    items: 0,
    subscriptions: 0,
    active_subscriptions: 0,
  }
  const items: { label: string; value: number }[] = [
    { label: "Users", value: stats.users ?? 0 },
    { label: "Organizations", value: stats.organizations ?? 0 },
    { label: "Items", value: stats.items ?? 0 },
    { label: "Subscriptions", value: stats.subscriptions ?? 0 },
    { label: "Active", value: stats.active_subscriptions ?? 0 },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      {items.map((item) => (
        <Card key={item.label}>
          <CardHeader>
            <CardDescription>{item.label}</CardDescription>
            <CardTitle className="text-3xl">{item.value}</CardTitle>
          </CardHeader>
        </Card>
      ))}
    </div>
  )
}

function OrganizationsTab() {
  const { data } = useQuery({
    queryKey: ["admin-organizations"],
    queryFn: featureApi.adminOrganizations,
  })

  const organizations = data?.data ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organizations ({organizations.length})</CardTitle>
        <CardDescription>
          All tenants on the platform and their member counts.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Members</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {organizations.map((org) => (
              <TableRow key={org.id}>
                <TableCell className="font-medium">{org.name}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{org.slug}</Badge>
                </TableCell>
                <TableCell>{org.member_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function Admin() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Admin Console</h1>
        <p className="text-muted-foreground">
          Platform overview, user accounts and tenants
        </p>
      </div>
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="organizations">Organizations</TabsTrigger>
          <TabsTrigger value="audit">Audit log</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab />
        </TabsContent>
        <TabsContent value="users">
          <div className="flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Users</h2>
                <p className="text-muted-foreground">
                  Manage user accounts and permissions
                </p>
              </div>
              <AddUser />
            </div>
            <UsersTable />
          </div>
        </TabsContent>
        <TabsContent value="organizations">
          <OrganizationsTab />
        </TabsContent>
        <TabsContent value="audit">
          <AuditLogTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function AuditLogTab() {
  const query = useQuery({
    queryKey: ["admin-audit-log"],
    queryFn: featureApi.adminAuditLog,
  })
  const entries = query.data?.data ?? []
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Audit log</h2>
        <p className="text-muted-foreground">
          Recent platform-wide audit events
        </p>
      </div>
      <Card>
        <CardContent className="pt-6">
          {query.isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : entries.length === 0 ? (
            <p className="text-muted-foreground">No audit events yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Action</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Organization</TableHead>
                  <TableHead className="text-right">When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell>
                      <code className="text-xs">{entry.action}</code>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.user_id ? entry.user_id.slice(0, 8) : "-"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.organization_id
                        ? entry.organization_id.slice(0, 8)
                        : "-"}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground">
                      {entry.created_at
                        ? new Date(entry.created_at).toLocaleString()
                        : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
