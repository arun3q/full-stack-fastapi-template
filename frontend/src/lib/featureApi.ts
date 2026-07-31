import { OpenAPI } from "@/client"

const API_V1 = "/api/v1"
const TOKEN_KEY = "access_token"

export type PlanPublic = {
  id: string
  name: string
  slug: string
  description: string | null
  amount_cents: number
  currency: string
  billing_interval: string
  is_active: boolean
  features: string | null
}

export type SubscriptionPublic = {
  id: string
  plan: PlanPublic | null
  provider: string
  status: string
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}

export type UserAccess = {
  role: string
  is_superuser: boolean
  is_verified: boolean
  plan: PlanPublic | null
  features: string[]
}

export type PublicConfig = {
  project_name: string
  support_email: string | null
}

export type OrganizationPublic = {
  id: string
  name: string
  slug: string
  created_at: string | null
}

export type MyOrganizationPublic = OrganizationPublic & {
  role: string
}

export type OrganizationMemberPublic = {
  id: string
  user_id: string
  email: string | null
  full_name: string | null
  role: string
  created_at: string | null
}

export type OrganizationInvitePublic = {
  id: string
  organization_id: string
  email: string
  role: string
  status: string
  created_at: string | null
}

export type NotificationPublic = {
  id: string
  type: string
  title: string
  body: string | null
  read_at: string | null
  created_at: string | null
}

export type AdminOverview = {
  users: number
  organizations: number
  items: number
  subscriptions: number
  active_subscriptions: number
}

export type ChatMessageInput = {
  role: string
  content: string
}

type ApiErrorBody = { detail?: string }

const ORG_KEY = "active_org_id"

export function getActiveOrgId(): string | null {
  return localStorage.getItem(ORG_KEY)
}

export function setActiveOrgId(id: string | null): void {
  if (id) localStorage.setItem(ORG_KEY, id)
  else localStorage.removeItem(ORG_KEY)
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY)
  const headers: Record<string, string> = {}
  if (token) headers.Authorization = `Bearer ${token}`
  const orgId = getActiveOrgId()
  if (orgId) headers["X-Organization-ID"] = orgId
  return headers
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${OpenAPI.BASE}${API_V1}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = (await response
      .json()
      .catch(() => null)) as ApiErrorBody | null
    if (response.status === 401 || response.status === 403) {
      localStorage.removeItem(TOKEN_KEY)
    }
    throw new Error(
      body?.detail ?? `Request failed with status ${response.status}`,
    )
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export const featureApi = {
  authProviders: () =>
    request<{ providers: string[] }>("/auth/providers", { method: "GET" }),

  userAccess: () => request<UserAccess>("/users/me/access", { method: "GET" }),

  plans: () =>
    request<{ data: PlanPublic[]; count: number }>("/payments/plans", {
      method: "GET",
    }),

  createCheckout: (planId: string) =>
    request<{ id: string; url: string }>(
      `/payments/checkout?plan_id=${encodeURIComponent(planId)}`,
      { method: "POST" },
    ),

  subscription: () =>
    request<SubscriptionPublic | null>("/payments/subscription", {
      method: "GET",
    }),

  cancelSubscription: () =>
    request<{ message: string }>("/payments/subscription/cancel", {
      method: "POST",
    }),

  billingPortal: () =>
    request<{ url: string }>("/payments/portal", { method: "POST" }),

  aiHealth: () =>
    request<{ provider: string | null; configured: boolean; model?: string }>(
      "/ai/health",
      { method: "GET" },
    ),

  publicConfig: () =>
    request<PublicConfig>("/public/config", { method: "GET" }),

  organizations: () =>
    request<{ data: MyOrganizationPublic[]; count: number }>(
      "/organizations/",
      {
        method: "GET",
      },
    ),

  createOrganization: (name: string) =>
    request<OrganizationPublic>("/organizations/", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  updateOrganization: (orgId: string, name: string) =>
    request<OrganizationPublic>(`/organizations/${orgId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),

  organizationMembers: (orgId: string) =>
    request<{ data: OrganizationMemberPublic[]; count: number }>(
      `/organizations/${orgId}/members`,
      { method: "GET" },
    ),

  organizationInvites: (orgId: string) =>
    request<{ data: OrganizationInvitePublic[]; count: number }>(
      `/organizations/${orgId}/invites`,
      { method: "GET" },
    ),

  inviteMember: (orgId: string, email: string, role = "member") =>
    request<OrganizationInvitePublic>(`/organizations/${orgId}/members`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),

  acceptInvite: (token: string) =>
    request<{ message: string }>(`/organizations/invites/${token}/accept`, {
      method: "POST",
    }),

  changeMemberRole: (orgId: string, userId: string, role: string) =>
    request<OrganizationMemberPublic>(
      `/organizations/${orgId}/members/${userId}?role=${encodeURIComponent(role)}`,
      { method: "PATCH" },
    ),

  removeMember: (orgId: string, userId: string) =>
    request<{ message: string }>(`/organizations/${orgId}/members/${userId}`, {
      method: "DELETE",
    }),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/users/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  resendVerificationEmail: (email: string) =>
    request<{ message: string }>("/users/verify-email/resend", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  notifications: () =>
    request<{ data: NotificationPublic[]; count: number }>("/notifications/", {
      method: "GET",
    }),

  notificationUnreadCount: () =>
    request<{ count: number }>("/notifications/unread-count", {
      method: "GET",
    }),

  markNotificationRead: (id: string) =>
    request<NotificationPublic>(`/notifications/${id}/read`, {
      method: "POST",
    }),

  markAllNotificationsRead: () =>
    request<{ count: number }>("/notifications/read-all", { method: "POST" }),

  adminOverview: () =>
    request<AdminOverview>("/admin/overview", { method: "GET" }),
}

export type StreamChatOptions = {
  messages: ChatMessageInput[]
  systemPrompt?: string
  signal?: AbortSignal
  onToken: (token: string) => void
  onDone?: () => void
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const response = await fetch(`${OpenAPI.BASE}${API_V1}/ai/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      messages: options.messages,
      system_prompt: options.systemPrompt,
    }),
    signal: options.signal,
  })
  if (!response.ok) {
    const body = (await response
      .json()
      .catch(() => null)) as ApiErrorBody | null
    throw new Error(
      body?.detail ?? `Chat failed with status ${response.status}`,
    )
  }

  const reader = response.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""
    for (const event of events) {
      if (!event.startsWith("data: ")) continue
      try {
        const payload = JSON.parse(event.slice(6)) as {
          token?: string
          event?: string
        }
        if (payload.token) {
          options.onToken(payload.token)
        } else if (payload.event === "done") {
          options.onDone?.()
        }
      } catch {
        // ignore malformed event
      }
    }
  }
}
