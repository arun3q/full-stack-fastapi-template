# Project Plan — Production-Gap Closure

Analysis + recommendations + phased implementation plan for closing the remaining
production gaps identified by a multi-agent audit of the enterprise/multi-tenant
SaaS stack (billing, tenants, RBAC, caching, DB, replicas, deployment).

Status legend: `[ ]` pending · `[x]` in progress · `[x]` done
Branch: `feat/enterprise-template-upgrades`

---

## Phase 1 — Security & correctness (do first; bugs, not features)

- [x] **Dunning cron actually sends email** — `subscription_dunning_job`
      (`core/jobs/maintenance.py:57`) only logs; send the past-due email, dedupe
      per org per day, update `Subscription.status` only when provider says so.
- [x] **Webhook retry scanner** — `WebhookDelivery.next_retry_at` is written but
      never read; add a cron job that re-queues stale `pending` deliveries whose
      `next_retry_at` passed (covers worker downtime during the retry window).
- [x] **RBAC on billing/credentials/files** — require `billing:manage` on
      `/payments/checkout`, `/payments/subscription/cancel`, `/payments/portal`;
      require `billing:manage` (or a new `apikey:*` / `file:*` permission) on
      `/api-keys/*` and `/files/upload`. Today a **viewer** can cancel the org's
      subscription, mint/revoke API keys, and upload files.
- [x] **CSRF protection for cookie auth mode** — `AUTH_TOKEN_IN_COOKIE` has no
      CSRF token; add double-submit cookie or require a custom header on
      state-changing requests when cookie mode is on.
- [x] **Rate-limit sensitive auth endpoints** — TOTP enable/disable, `/auth/refresh`,
      `/auth/logout`, SAML login/ACS, and API-key auth are unthrottled.
- [x] **Production rate-limit storage** — default is `memory://` (per process);
      the image runs 4 workers. Set `RATE_LIMIT_STORAGE=redis://...` in compose
      + deploy docs.
- [x] **Security headers** — add a Traefik headers middleware (HSTS,
      X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy).
- [x] **Readiness probe** — health endpoint is liveness-only
      (`utils.py:30` returns `True`); add DB + Redis checks, gate the LB probe on it.
- [x] **API-key hashing** — unsalted SHA-256; move to HMAC-SHA256 with a server
      pepper (or scrypt) so a DB leak doesn't enable offline brute force.
- [x] **SAML hardening** — validate/echo `RelayState` + return-to allowlist; rate
      limit login/ACS; avoid leaking IdP error strings.

## Phase 2 — Billing completeness (usage, plans, lifecycle)

- [x] **Usage metering backbone** — `UsageEvent` model + a generic
      `check_quota(org, meter, amount)` helper; meter AI calls, file storage,
      API-key/webhook usage; enforce quotas beyond items/seats.
- [x] **Plan changes & trials** — `trial_days` on `Plan`; Stripe
      `trial_period_days`; upgrade/downgrade via provider subscription-update with
      proration; seat quantity synced to member count (Stripe quantity + Razorpay).
- [x] **Invoice/tax/refund handling** — handle `invoice.payment_succeeded`,
      `charge.refunded`; persist invoices; surface tax IDs.
- [x] **Per-tenant revenue** — add `PaymentEvent.organization_id` and MRR/ARR
      aggregation in the admin overview.
- [x] **Subscription lifecycle webhooks** — dispatch outbound events on
      subscription.created/updated/canceled, invoice.paid/failed (today only
      `webhook.test` fires).
- [x] **Single-active-subscription guard** — reject `/checkout` if the org already
      has an active/trialing subscription.

## Phase 3 — Multi-tenant lifecycle & compliance

- [x] **Tenant suspension + deletion + GDPR export** — `Organization.is_active`,
      `DELETE /organizations/{id}` (owner, with cascade + audit), data-export
      endpoint; suspension blocks sign-in and revokes sessions/keys.
- [x] **Invite management** — revoke/cancel/resend/decline endpoints + UI;
      mark `INVITE_DECLINED` on decline.
- [x] **Ownership** — owner transfer, leave-org, last-owner protection.
- [x] **RLS applied via migration (opt-in)** — policies for
      `organizationmember` + `organizationinvite`; set tenant GUC in more request
      paths (notifications, sessions, api-keys, SCIM).
- [x] **SSO-forced orgs / domain auto-join** (stretch) — per-org SAML binding,
      "SSO required" flag, email-domain auto-join.

## Phase 4 — Caching & database hardening

- [x] **Cache invalidation** — `cache_delete` on plan/branding/subscription/access
      changes; stampede protection; scope idempotency keys by path+user; don't
      cache error responses.
- [x] **Cache `get_active_plan` per org** (short TTL, invalidate on subscription
      change) — it hits the DB on every item write, invite, and plan gate.
- [x] **Missing indexes migration** — `Item.organization_id`, `Session.user_id`,
      `OrganizationMember.user_id`, `Subscription.organization_id`/`plan_id`,
      `WebhookDelivery.webhook_id`/`status`/`next_retry_at`, `created_at` sort
      columns, `OrganizationInvite(status, expires_at)`.
- [x] **Kill N+1** — admin org member counts via `GROUP BY`; member list via join;
      "my orgs" via one query.
- [x] **Engine hardening** — `pool_recycle`, connect/statement timeouts; add a
      runnable PgBouncer service (transaction mode) to compose.prod.
- [x] **Job observability** — DLQ/retry for `process_payment_event_job`; longer
      `keep_result`; job queue metrics.

## Phase 5 — Deployment & observability

- [x] **Production compose** (`compose.prod.yml`) — PgBouncer, Prometheus,
      security headers, worker healthcheck, backend `start_period`.
- [x] **CD hardening** — tag images with commit SHA, `--pull`, post-deploy health
      wait, migration check, rollback automation (previous image).
- [x] **OTel OTLP** — configurable exporter endpoint instead of console.
- [x] **Protect `/metrics`** — auth or network restriction.

## Phase 6 — Frontend & DX

- [x] **Auth lifecycle** — auto-refresh with the refresh token (silent refresh /
      401 retry), or switch to httpOnly-cookie mode; stop hard logout after 8 days.
- [x] **Error UX** — per-page error boundaries; surface non-401 fetch errors
      (toast) at the QueryCache layer.
- [x] **Env config validation** — zod-validated `VITE_*` config with defaults.
- [x] **Playwright coverage** — billing, members/invites, chat, admin overview,
      2FA, i18n switching, marketing pages.

---

## How to work this file
- Implement in phase order; each item is verified by pytest + ruff/mypy/ty and the
  frontend build before ticking it.
- Cross-reference `PROJECT_ROADMAP.md` (feature phases) and `ops.md` (ops runbook).
- Update this file as items complete; never delete history.

## Post-implementation verification (agent review, 2026-08-01)
All six phases implemented; a full agent review found 1 false positive + 10 real
findings, all fixed and re-verified:

| # | Finding | Fix | Status |
|---|---------|-----|--------|
| B1 | `deps.py:64` flagged as Python 2 syntax | False positive — `except A, B:` is valid PEP 758 syntax on the project's Python 3.14 target; confirmed imports cleanly in the 3.14 container | N/A |
| H1 | Cross-tenant org ops (suspend/delete/export/invites/ownership/leave) used header-scoped permission | Switched to path-scoped `_require_permission`; regression test added | Done |
| H2 | Webhook SSRF (private/metadata targets) | `validate_webhook_url` on create/update | Done (residual DNS-rebinding noted) |
| H3 | Metered quotas never reset | `check_quota` uses the monthly window | Done |
| M1 | AI metering ran on a closed session in SSE generator | Fresh `async_session_factory()` inside the generator | Done |
| M2 | Frontend refresh loop (403) + single-use-token race | Refresh only on 401; single-flight guard | Done |
| M3 | Idempotency key collided across tenants | Key scoped to `X-Organization-ID` + token fingerprint | Done |
| M4 | Rate limits shared behind proxy | `X-Forwarded-For`-aware key (trusted-proxy only) | Done |
| L1 | Webhook non-2xx treated as permanent failure | Retry on HTTP errors with backoff | Done |
| L2 | Active-plan cache not invalidated on webhook reconcile | `invalidate_active_plan` in payment job | Done |
| L5 | OAuth/SAML logins had no refresh token | Sessions created + `&refresh=` in redirect; frontend stores both | Done |
| L4 | Dunning daily repeat | Accepted (standard dunning cadence); notifications dedupe per run | Documented |

Known residual caveats (acceptable for template): DNS-rebinding on webhook URLs
(hostname→private-IP at delivery time), XFF spoofing if the proxy doesn't strip
the header, idempotency fingerprint changes after token rotation.
