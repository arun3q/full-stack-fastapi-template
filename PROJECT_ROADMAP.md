# Project Roadmap — Enterprise Multi-Tenant SaaS Template

This document is the **source of truth** for the phased build-out of this template.
Tick items off as they are implemented and verified. Keep this file updated on
every change so future sessions can pick up exactly where we left off.

Status legend: `[x]` done · `[ ]` pending · `[~]` in progress

Branch: `feat/enterprise-template-upgrades`

---

## ✅ Done before this roadmap

- [x] Fully async backend (SQLModel `AsyncSession` + tuned connection pool)
- [x] Background jobs (ARQ + Redis worker) — emails + payment webhooks
- [x] Stripe + Razorpay billing behind a `PaymentProvider` interface
- [x] Social OAuth (Authlib): Google, LinkedIn, Meta, GitHub + `oauth_account` table
- [x] AI/LLM streaming (SSE) — OpenAI-compatible + Anthropic
- [x] Global RBAC: `User.role` (user/staff/admin), `require_roles`, `require_plan`,
      `GET /users/me/access`, `is_verified` flag, migration `d7e5f3a9b1c2`
- [x] Frontend: OAuth buttons, `/auth/callback`, Billing page, AI Chat page,
      accent themes, sidebar nav
- [x] README + `enterprise-features.md` documentation
- [x] Full verification green: ruff, format, mypy, ty, 77 pytest, frontend build/tsc/biome

---

## Phase 1 — Drop-in SaaS core

Goal: a public marketing experience, account hardening, and the multi-tenant
foundation (organizations + members + invites) with tenant-scoped data, org-level
subscriptions and plan-driven quotas.

### 1.1 Route restructure (public vs app)
- [x] Move authenticated app from `/` to `/dashboard`
- [x] `/` becomes the public marketing landing page (no auth)
- [x] Update auth redirects: login/signup success → `/dashboard`; logged-in users
      from `/` → `/dashboard`; 401 handler → `/login`
- [x] Sidebar + nav updated for `/dashboard`

### 1.2 Public marketing pages
- [x] Marketing layout (top nav: logo, Features, Pricing, Sign in / Get started; footer)
- [x] Landing page: hero, feature grid, pricing section (from `GET /payments/plans`), CTA
- [x] `/pricing` page reusing the public plans endpoint
- [x] `/terms`, `/privacy` placeholder pages
- [x] Public config endpoint `GET /api/v1/public/config` (project name, support email) for branding
- [x] Brand name rendered from config (fallback to logo)

### 1.3 Email verification
- [x] Verify-email token generation + `POST /users/verify-email` endpoint
- [x] Resend endpoint `POST /users/verify-email/resend`
- [x] Signup sends verification email; `is_verified` wired to the flow
- [x] Email templates (build from `email-templates/src`)
- [x] Tests

### 1.4 Tenant foundation
- [x] Models: `Organization`, `OrganizationMember`, `OrganizationInvite` + migration
- [x] Personal organization auto-created for every user (in `crud.create_user`)
- [x] `CurrentOrg` dependency (active tenant via `X-Organization-ID` header, default = personal org)
- [x] Org permission registry + `require_org_permission(...)` dependency
- [x] Org endpoints: list/create/detail/update members/invite/accept/remove/change-role
- [x] Tests

### 1.5 Tenant-scoped items
- [x] `Item.organization_id` column
- [x] Items CRUD scoped to the active organization
- [x] Test helpers updated; tests pass

### 1.6 Org-level subscriptions
- [x] `Subscription.organization_id` (subscriptions belong to the organization)
- [x] Checkout/webhook/reconcile/read/cancel/portal → organization
- [x] `get_active_plan` resolves via the active organization
- [x] Tests

### 1.7 Plan-driven quotas
- [x] `Plan.quotas` JSON column (e.g. `{"max_items": 5, "max_seats": 1}`)
- [x] Default plans carry quotas (free/pro/business/enterprise)
- [x] Items quota + seats quota enforced from plan config (replaces `MAX_FREE_ITEMS`)
- [x] Tests

### 1.8 Frontend org & account UX
- [x] Org switcher in the sidebar (list/create orgs, switch active org)
- [x] Members & invites page (invite by email, accept, roles, remove)
- [x] Billing page shows the organization's subscription
- [x] Email-verification banner / resend UI
- [x] Marketing pages polished (responsive, dark mode, accent-aware)

### 1.9 Verification & docs
- [x] ruff / format / mypy / ty / pytest green
- [x] Frontend build + tsc + biome green
- [x] README + this roadmap updated; commit + push to `arun3q`

---

## Phase 2 — Enterprise hardening

Goal: production-grade platform engineering — security, observability, integrations.

- [x] Rate limiting (`slowapi`) per user/IP — applied to login & password recovery
- [x] Refresh tokens + rotation + revocation, logout revocation (DB-backed sessions)
- [x] Session management (list/revoke sessions)
- [x] Audit log (`auditlog` table) — wired into login, TOTP, admin user, org, file actions
- [x] Structured JSON logging (`LOG_FORMAT=json`) + `X-Request-ID` correlation
- [x] OpenTelemetry tracing (optional `ENABLE_OTEL` toggle — request spans)
- [x] Permission registry → granular `require_org_permission("org:update")` matrix
- [x] Idempotency keys on POST/PUT/PATCH (`Idempotency-Key` middleware, Redis)
- [x] Outbound webhooks (signed, retries + backoff, delivery log, test dispatch)
- [x] API keys / service accounts (hashed, scoped, `X-API-Key` auth + management)
- [x] ARQ cron jobs: expired-invite/session cleanup, subscription dunning
- [x] Keyset/cursor pagination — helper + applied to items
- [x] Redis caching for hot reads (plans, public config)
- [x] S3/MinIO-backed file uploads (`/files/upload`)
- [x] httpOnly session-cookie auth option (`AUTH_TOKEN_IN_COOKIE`)
- [x] Login security: failed-login lockout (Redis) + TOTP 2FA
- [x] Admin console: API (overview/orgs/users/audit) + frontend tabs (Overview/Users/Organizations)

## Phase 3 — Scale & compliance

Goal: hard multi-tenant isolation, enterprise identity, growth UX.

- [~] Postgres Row-Level Security (RLS) — opt-in `ENABLE_RLS` GUC hook wired
      (tenant + admin flags per request); policies documented in `ops.md`
- [x] Read replicas + PgBouncer — `READ_REPLICA_URL` wired (read engine +
      `get_read_session` on list/admin/plan reads); PgBouncer documented in `ops.md`
- [x] Keyset pagination across list endpoints — items, users, admin orgs/audit-log
- [x] Prometheus metrics (`/metrics` + request counters/histograms)
- [x] SSO (SAML) via python3-saml + SCIM 2.0 provisioning (users/groups)
- [x] Per-tenant branding — `Organization.branding` + API + frontend accent wiring
- [x] Notifications center (backend + notification bell UI + unread count)
- [x] i18n framework (i18next/react-i18next) — en+es locales + language switcher
- [x] Onboarding wizard (create org → invite → subscribe)
- [x] Backup/PITR + restore runbook; deploy/rollback notes (`ops.md`)

---

## Architecture cleanup (SOLID) — done

- [x] Split `PaymentProvider` into `CheckoutProvider` + optional `BillingPortalProvider` (ISP)
- [x] Split `core/jobs.py` into `core/jobs/` package (emails, payments, webhooks, maintenance)
- [x] Split `core/middleware.py` into `core/middleware/` package
- [x] Repository layer: `app/crud/` package; routes refactored to thin orchestration
- [x] Frontend folds `featureApi.ts` onto the regenerated OpenAPI client (single transport)

---

## How to work this file

- When starting a session: `git log --oneline -5`, then read this roadmap to see
  where we left off.
- Tick `[x]` only after the item is implemented **and** verified green.
- Add new work as new sub-bullets under the relevant phase; never delete history.
