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

export type ChatMessageInput = {
  role: string
  content: string
}

type ApiErrorBody = { detail?: string }

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
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
