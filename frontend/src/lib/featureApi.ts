import {
  AdminService,
  AiService,
  ApiKeysService,
  AuthService,
  NotificationsService,
  OpenAPI,
  OrganizationsService,
  PaymentsService,
  PublicService,
  UsersService,
  WebhooksService,
} from "@/client"

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
  branding: string | null
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

const TOKEN_KEY = "access_token"
const REFRESH_KEY = "refresh_token"
const ORG_KEY = "active_org_id"

export function getActiveOrgId(): string | null {
  return localStorage.getItem(ORG_KEY)
}

export function setActiveOrgId(id: string | null): void {
  if (id) localStorage.setItem(ORG_KEY, id)
  else localStorage.removeItem(ORG_KEY)
}

export function storeTokens(
  accessToken: string,
  refreshToken?: string | null,
): void {
  localStorage.setItem(TOKEN_KEY, accessToken)
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

/** The generated client sends the active tenant on every request. */
export function configureOpenApi() {
  OpenAPI.TOKEN = async () => localStorage.getItem(TOKEN_KEY) || ""
  OpenAPI.HEADERS = async (): Promise<Record<string, string>> => {
    const headers: Record<string, string> = {}
    const orgId = getActiveOrgId()
    if (orgId) headers["X-Organization-ID"] = orgId
    return headers
  }
}

/**
 * Exchange the stored refresh token for a fresh access token pair.
 * Returns true on success; used to silently recover from a 401.
 */
export async function refreshSession(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  try {
    const response = await fetch(`${OpenAPI.BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!response.ok) {
      clearTokens()
      return false
    }
    const data = await response.json()
    storeTokens(data.access_token, data.refresh_token)
    return true
  } catch {
    return false
  }
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) headers.Authorization = `Bearer ${token}`
  const orgId = getActiveOrgId()
  if (orgId) headers["X-Organization-ID"] = orgId
  return headers
}

type ListResponse<T> = { data: T[]; count: number }

export const featureApi = {
  authProviders: async () =>
    (await AuthService.authProviders()) as unknown as { providers: string[] },
  userAccess: async () =>
    (await UsersService.readUserAccess()) as unknown as UserAccess,
  plans: async () =>
    (await PaymentsService.readPlans()) as unknown as ListResponse<PlanPublic>,
  createCheckout: async (planId: string) =>
    (await PaymentsService.createCheckout({ planId })) as unknown as {
      id: string
      url: string
    },
  subscription: async () =>
    (await PaymentsService.readSubscription()) as unknown as SubscriptionPublic | null,
  cancelSubscription: async () =>
    (await PaymentsService.cancelSubscription()) as unknown as {
      message: string
    },
  billingPortal: async () =>
    (await PaymentsService.billingPortal()) as unknown as { url: string },
  changePlan: async (planId: string) =>
    (await PaymentsService.changePlan({
      planId,
    })) as unknown as SubscriptionPublic,
  usage: async () =>
    (await PaymentsService.getUsageMetrics()) as unknown as Record<
      string,
      { used: number; limit: number } | string | null
    >,
  aiHealth: async () =>
    (await AiService.aiHealth()) as unknown as {
      provider: string | null
      configured: boolean
      model?: string
    },
  publicConfig: async () =>
    (await PublicService.publicConfig()) as unknown as PublicConfig,
  organizations: async () =>
    (await OrganizationsService.readMyOrganizations()) as unknown as ListResponse<MyOrganizationPublic>,
  createOrganization: async (name: string) =>
    (await OrganizationsService.createOrganizationRoute({
      requestBody: { name },
    })) as unknown as OrganizationPublic,
  updateOrganization: async (orgId: string, name: string) =>
    (await OrganizationsService.updateOrganizationRoute({
      organizationId: orgId,
      requestBody: { name },
    })) as unknown as OrganizationPublic,
  organizationMembers: async (orgId: string) =>
    (await OrganizationsService.readMembers({
      organizationId: orgId,
    })) as unknown as ListResponse<OrganizationMemberPublic>,
  organizationInvites: async (orgId: string) =>
    (await OrganizationsService.readInvites({
      organizationId: orgId,
    })) as unknown as ListResponse<OrganizationInvitePublic>,
  inviteMember: async (orgId: string, email: string, role = "member") =>
    (await OrganizationsService.inviteMember({
      organizationId: orgId,
      requestBody: { email, role },
    })) as unknown as OrganizationInvitePublic,
  acceptInvite: async (token: string) =>
    (await OrganizationsService.acceptInvite({ token })) as unknown as {
      message: string
    },
  changeMemberRole: async (orgId: string, userId: string, role: string) =>
    (await OrganizationsService.updateMemberRoleRoute({
      organizationId: orgId,
      userId,
      role,
    })) as unknown as OrganizationMemberPublic,
  removeMember: async (orgId: string, userId: string) =>
    (await OrganizationsService.removeMemberRoute({
      organizationId: orgId,
      userId,
    })) as unknown as { message: string },
  revokeInvite: async (orgId: string, inviteId: string) =>
    (await OrganizationsService.revokeInvite({
      organizationId: orgId,
      inviteId,
    })) as unknown as { message: string },
  resendInvite: async (orgId: string, inviteId: string) =>
    (await OrganizationsService.resendInvite({
      organizationId: orgId,
      inviteId,
    })) as unknown as OrganizationInvitePublic,
  declineInvite: async (token: string) =>
    (await OrganizationsService.declineInvite({ token })) as unknown as {
      message: string
    },
  suspendOrganization: async (orgId: string) =>
    (await OrganizationsService.suspendOrganization({
      organizationId: orgId,
    })) as unknown as OrganizationPublic,
  deleteOrganization: async (orgId: string) =>
    (await OrganizationsService.deleteOrganization({
      organizationId: orgId,
    })) as unknown as { message: string },
  exportOrganization: async (orgId: string) =>
    (await OrganizationsService.exportOrganization({
      organizationId: orgId,
    })) as unknown as Record<string, unknown>,
  transferOwnership: async (orgId: string, userId: string) =>
    (await OrganizationsService.transferOwnership({
      organizationId: orgId,
      userId,
    })) as unknown as { message: string },
  leaveOrganization: async (orgId: string) =>
    (await OrganizationsService.leaveOrganization({
      organizationId: orgId,
    })) as unknown as { message: string },
  verifyEmail: async (token: string) =>
    (await UsersService.verifyEmail({
      requestBody: { token },
    })) as unknown as { message: string },
  resendVerificationEmail: async (email: string) =>
    (await UsersService.resendVerificationEmail({
      requestBody: { email },
    })) as unknown as { message: string },
  notifications: async () =>
    (await NotificationsService.readNotifications()) as unknown as ListResponse<NotificationPublic>,
  notificationUnreadCount: async () =>
    (await NotificationsService.unreadCount()) as unknown as { count: number },
  markNotificationRead: async (id: string) =>
    (await NotificationsService.markReadRoute({
      notificationId: id,
    })) as unknown as NotificationPublic,
  markAllNotificationsRead: async () =>
    (await NotificationsService.markAllReadRoute()) as unknown as {
      count: number
    },
  adminOverview: async () =>
    (await AdminService.adminOverview()) as unknown as AdminOverview,
  adminOrganizations: async () =>
    (await AdminService.adminOrganizations()) as unknown as {
      data: {
        id: string
        name: string
        slug: string
        member_count: number
        created_at: string | null
      }[]
      count: number
    },
  adminAuditLog: async () =>
    (await AdminService.adminAuditLog()) as unknown as {
      data: {
        id: string
        action: string
        user_id: string | null
        organization_id: string | null
        created_at: string | null
      }[]
      count: number
    },
  apiKeys: async () =>
    (await ApiKeysService.readApiKeys()) as unknown as {
      data: {
        id: string
        name: string
        scopes: string[]
        last_used_at: string | null
        created_at: string | null
      }[]
      count: number
    },
  createApiKey: async (name: string, scopes: string[]) =>
    (await ApiKeysService.createApiKeyRoute({
      requestBody: { name, scopes },
    })) as unknown as { key: string },
  revokeApiKey: async (keyId: string) =>
    (await ApiKeysService.revokeApiKeyRoute({
      keyId,
    })) as unknown as { message: string },
  webhooks: async () =>
    (await WebhooksService.readWebhooks()) as unknown as {
      data: {
        id: string
        url: string
        events: string[]
        is_active: boolean
        created_at: string | null
      }[]
      count: number
    },
  createWebhook: async (url: string, events: string[]) =>
    (await WebhooksService.createWebhookRoute({
      requestBody: { url, events },
    })) as unknown as {
      id: string
      url: string
      events: string[]
      is_active: boolean
    },
  deleteWebhook: async (webhookId: string) =>
    (await WebhooksService.deleteWebhook({
      webhookId,
    })) as unknown as { message: string },
  webhookDeliveries: async (webhookId: string) =>
    (await WebhooksService.readDeliveries({
      webhookId,
    })) as unknown as {
      data: {
        id: string
        event: string
        status: string
        attempts: number
        created_at: string | null
      }[]
      count: number
    },
  sessions: async () =>
    (await AuthService.readSessions()) as unknown as {
      data: {
        id: string
        ip_address: string | null
        user_agent: string | null
        last_used_at: string | null
        created_at: string | null
      }[]
      count: number
    },
  revokeSession: async (sessionId: string) =>
    (await AuthService.revokeSessionRoute({
      sessionId,
    })) as unknown as { message: string },
  totpSetup: async (password: string) =>
    (await AuthService.totpSetup({
      requestBody: { password },
    })) as unknown as { otpauth_url: string; secret: string },
  totpEnable: async (code: string, password: string) =>
    (await AuthService.totpEnable({
      requestBody: { code, password },
    })) as unknown as { message: string },
  totpDisable: async (code: string) =>
    (await AuthService.totpDisable({
      requestBody: { code },
    })) as unknown as { message: string },
}

export type StreamChatOptions = {
  messages: ChatMessageInput[]
  systemPrompt?: string
  signal?: AbortSignal
  onToken: (token: string) => void
  onDone?: () => void
}

type ApiErrorBody = { detail?: string }

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const response = await fetch(`${OpenAPI.BASE}/api/v1/ai/chat`, {
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
