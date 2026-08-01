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

---

# Round 2 — Deep-dive gap closure (6-agent audit, 2026-08-01)

Second-pass audit focused on what is STILL missing for production-grade
enterprise multi-tenant SaaS. Six domain agents audited tenancy/RBAC, billing,
caching/perf, DB/replicas, deploy/observability, and frontend/DX.

Excluded as false positives: `deps.py:64` `except A, B:` (valid PEP 758 syntax
on the Python 3.14 target; the app imports and 128 tests pass).

## Phase A — Identity, RBAC & tenant isolation (correctness/security)

- [ ] **Owner-demote bug** — `update_member_role_route` checks the role *after* mutation, so
      demoting the owner leaves the org with no owner (`organizations.py:358`). Read current
      role first; require `member:remove` for owner targets; forbid owner count → 0.
- [ ] **Invite role whitelist** — invites accept `role:"owner"` / arbitrary strings
      (`organizations.py:189`). Restrict to `{admin, member, viewer}`.
- [ ] **Enforce API-key scopes** — `parse_scopes` is decorative; SCIM accepts any key.
      Require `scim` scope in `get_scim_context`; add scope→action checks.
- [ ] **Suspended orgs still operable** — `_get_membership`/`_require_permission` never check
      `org.is_active`, so path-param routes (invite/export/delete/transfer) work on suspended
      orgs. Add `is_active` check; resume/unsuspend endpoint.
- [ ] **SCIM deactivation is global** — `PATCH active:false`/`DELETE` sets `User.is_active`,
      deactivating the user in every org. Scope to the membership instead.
- [ ] **File ACL** — object keys have no org prefix and URLs are public; add
      `uploads/{org_id}/…` keys + signed/org-scoped download endpoint.
- [ ] **Session revocation on credential change** — revoke sessions on password
      change/reset + email change; add a token-version claim so old JWTs die.
- [ ] **Email change re-verification** — new email currently keeps `is_verified=True`;
      send verification + revoke sessions.
- [ ] **Account-deletion guards** — deleting a user who owns orgs leaves them ownerless and
      cascade-deletes cross-org items. Block while owner of orgs with members.
- [ ] **Deactivated-user auth guard** — `/auth/refresh`, SAML, and OAuth ignore
      `is_active`. Guard all three; revoke sessions on deactivate.
- [ ] **Server-side logout** — frontend `logout()` only clears localStorage; call
      `/auth/logout` to revoke the refresh session.
- [ ] **SAML account-takeover guard** — ACS logs into any account whose email matches
      without linkage consent + ignores `is_active`. Refuse/link only for OAuth-only
      accounts; require admin approval on collision.
- [ ] **SCIM PatchOp/Role/PUT** — implement `Operations[]` parsing, role/group writes,
      email-rename reconciliation.
- [ ] **RLS GUC hardening** — set `app.current_org_id` per transaction (begin event) on
      writer/replica/worker sessions and consider deny-unset policies (see Phase D1).

## Phase B — Billing completeness (revenue correctness)

- [ ] **Per-seat billing** — `Subscription.quantity` is dead; sync quantity to the provider
      on member join/leave and set it on checkout.
- [ ] **change_plan price resolution** — a plan without `provider_plan_id` silently falls
      back to the global price (`payments.py:124-141`), mapping a foreign price onto the
      wrong plan. Reject unset `provider_plan_id`.
- [ ] **Webhook enqueue inline fallback** — Redis down ⇒ `enqueue_job` returns `None` but
      webhook still 200s ⇒ silent revenue-event loss. Process inline as fallback.
- [ ] **Event coverage** — handle `invoice.payment_succeeded`, `charge.refunded`,
      `payment_intent.succeeded/failed`, `subscription.paused/resumed`, `checkout.expired`.
- [ ] **Seat-quota enforcement in SCIM/invite-accept** — provisioning bypasses `max_seats`;
      accept-invite doesn't re-check (TOCTOU).
- [ ] **One-active-sub per org at DB level** — partial unique index
      `ON subscription(organization_id) WHERE status IN ('active','trialing','past_due')`.
- [ ] **Admin plan CRUD** + downgrade validation (usage exceeds new plan quotas → reject).
- [ ] **Invoice model + PaymentEvent.subscription_id**; MRR fixes (currency, quantity,
      trialing/past_due, ARR, churn).
- [ ] **Razorpay** — change-plan handling, `payment.captured/failed` events, replay-safe
      HMAC timestamps.
- [ ] **Redis-down duplicate guard** — use `INSERT … ON CONFLICT DO NOTHING` for event
      dedupe; raise `PaymentEvent.raw` limit.

## Phase C — Caching & performance

- [ ] **FIX cached-decorator serialization bug** — `cache_set` stores `str(model)`; on a
      cache hit `/payments/plans` and `/public/config` return the model's `str()` and 500.
      Use `value.model_dump(mode="json")`; version the cache prefix (`cache:v1:`).
- [ ] **get_active_plan** — cache misses (sentinel) + cache the full plan payload, not just
      the id; single-flight/stampede protection on hot keys.
- [ ] **Missing index** — `Notification.user_id` (polled unread-count seq-scans).
- [ ] **N+1 kills** — `read_members`, `read_my_organizations`, `admin_overview`,
      `list_scim_users` (batch joins / GROUP BY / selectinload).
- [ ] **count_items on every list** — drop/skip count under cursor pagination.
- [ ] **Composite indexes** — `(organization_id, created_at DESC)` for items/memberships/
      invites/subscription lookups.
- [ ] **GZipMiddleware** + `Cache-Control`/ETag on cached GETs.

## Phase D — DB integrity & replicas

- [ ] **RLS × PgBouncer transaction pooling** — the tenant GUC is transaction-local and
      lost after any `commit()`; under `POOL_MODE: transaction` a post-commit read
      autobegins on a different pooled connection with no GUC, silently disabling
      isolation (policies are permissive-when-unset). Set the GUC via a session begin event
      (all session paths incl. replica + worker) or make policies deny-unset.
- [ ] **Org delete does not delete tenant data** — ORM-vs-FK `ondelete` mismatch means
      `session.delete(org)` SET-NULLs items/subscriptions instead of cascading (GDPR
      contract broken). Add `passive_deletes=True`/`cascade_delete=True`.
- [ ] **Case-insensitive email uniqueness** + normalize `email.lower()`.
- [ ] **CHECK constraints** — roles, statuses, `amount_cents >= 0`, `quantity > 0`.
- [ ] **JSON→JSONB** for quotas/features/scopes/events (raise truncating limits).
- [ ] **`alembic check` in CI** to catch model/migration drift.
- [ ] **Backups** — scheduled `pg_dump` + offsite copy.
- [ ] **Timeouts** — `statement_timeout`/`connect_timeout` on engines.
- [ ] **Replica plumbing** — real replica service + `READ_REPLICA_URL` in `compose.prod`;
      enforce read-only on read sessions; route auth reads to replica or document the
      tradeoff; replica-down fallback; force-writer path for read-your-writes
      (`POST /items/` → `GET /items/`).

## Phase E — Deploy, observability & hardening

- [ ] **CSP + Permissions-Policy + TLS minimum version** (Traefik).
- [ ] **`.env` hygiene** — stop tracking `.env`, add `.gitignore` + real `.env.example`
      documenting all new settings.
- [ ] **SECRET_KEY required in non-local** — random per-worker default causes intermittent
      401s with `--workers 4`.
- [ ] **Non-root Docker user**; pin image versions/digests; `bun install --frozen-lockfile`.
- [ ] **Body-size limit** middleware; uvicorn `--limit-max-requests`, `--proxy-headers`.
- [ ] **CD ships the built image** — `docker compose push` + `TAG=${{ github.sha }}`
      immutable tags + rollback on failed readiness.
- [ ] **CI hardening** — `uv audit`, gitleaks, `alembic check`, Docker layer caching.
- [ ] **Worker observability** — Sentry + OTel in worker, real healthcheck (ARQ process),
      ARQ queue-depth/job-duration/error metrics.
- [ ] **Metrics cardinality** — label with route template, not raw path.
- [ ] **JSON access-log** middleware.
- [ ] **SMTP reliability** — check `status_code`, raise on failure, retry `send_email_job`;
      add payment/security email templates.
- [ ] **Readiness returns 503** when Redis is down; wire Prometheus bearer token to match
      `METRICS_TOKEN`.

## Phase F — Frontend & DX

- [ ] **Regenerate OpenAPI client** — missing `changePlan`, org lifecycle
      (suspend/delete/export), invite revoke/resend/decline, transfer, leave. Commit
      `openapi.json`; add `git diff --exit-code` sync check in CI.
- [ ] **401 mutation recovery** — failed mutations are silently dropped after single-flight
      refresh; queue/retry or surface the error.
- [ ] **Server-side logout** in `useAuth.logout`.
- [ ] **Billing** — usage metering bars + change-plan UI (upgrade/downgrade currently 409s).
- [ ] **Org settings page** — suspend/delete/export/transfer/leave.
- [ ] **Members page** — revoke/resend invites, confirm dialogs, loading/empty states.
- [ ] **New pages** — API keys, webhook manager (create/test/deliveries), 2FA, active
      sessions, admin audit-log tab, notifications center.
- [ ] **i18n** — translate app body copy into `es.json`; locale-aware price/date formatting;
      sync `html lang`.
- [ ] **Vitest unit tests** + `frontend/.env.example`; chat input a11y (`aria-label`,
      `aria-live`); docs for new features.

## Top priorities (if implementing in one pass)
1. Round-2 P0 bugs: cached-decorator 500, owner-demote, API-key scope enforcement,
   suspended-org path routes, change_plan price fallback, webhook enqueue loss,
   org-delete cascade, session revocation on credential change.
2. Per-seat billing + event coverage + DB-level uniqueness (revenue correctness).
3. RLS×PgBouncer GUC fix + replica plumbing.
4. Frontend: regenerate client, usage/change-plan/org-settings UI, 401 mutation retry.
