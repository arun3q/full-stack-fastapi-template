# Full Stack FastAPI Template

<a href="https://github.com/fastapi/full-stack-fastapi-template/actions?query=workflow%3A%22Test+Docker+Compose%22" target="_blank"><img src="https://github.com/fastapi/full-stack-fastapi-template/workflows/Test%20Docker%20Compose/badge.svg" alt="Test Docker Compose"></a>
<a href="https://github.com/fastapi/full-stack-fastapi-template/actions?query=workflow%3A%22Test+Backend%22" target="_blank"><img src="https://github.com/fastapi/full-stack-fastapi-template/workflows/Test%20Backend/badge.svg" alt="Test Backend"></a>
<a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/fastapi/full-stack-fastapi-template" target="_blank"><img src="https://coverage-badge.samuelcolvin.workers.dev/fastapi/full-stack-fastapi-template.svg" alt="Coverage"></a>

> This branch extends the upstream [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)
> with production-ready SaaS features: a **fully async** backend, **background jobs**,
> **subscriptions & billing** (Stripe/Razorpay), **social login (OAuth)**, **AI/LLM
> streaming**, and a **themeable UI**. Everything is optional — the app works out of
> the box with each feature disabled, and lights up as you add configuration.

---

## Technology Stack and Features

**Backend — [FastAPI](https://fastapi.tiangolo.com) (Python 3.14)**

- 🧰 [SQLModel](https://sqlmodel.tiangolo.com) (SQLAlchemy-based ORM) + [PostgreSQL](https://www.postgresql.org).
- 🔍 [Pydantic](https://docs.pydantic.dev) for validation and settings.
- 🔁 **Fully async** request/response handling (`SQLModel.AsyncSession` on the
  `psycopg` async driver) with a tuned connection pool (`pool_pre_ping`,
  `pool_size`, `max_overflow`).
- 📨 **Background jobs** with [ARQ](https://arq-docs.helpmanual.io) + [Redis](https://redis.io):
  emails and payment-webhook processing run on a separate worker process.
- 💳 **Subscriptions & billing** with [Stripe](https://stripe.com) or [Razorpay](https://razorpay.com)
  behind a common `PaymentProvider` interface — checkout, webhooks, plans,
  subscriptions, billing portal.
- 🔑 **Social login (OAuth2)** with Google, LinkedIn, Meta (Facebook) and GitHub via [Authlib](https://authlib.org).
- 🤖 **AI / LLM streaming** (Server-Sent Events) with OpenAI-compatible APIs
  (OpenAI, Groq, Ollama, vLLM, …) and [Anthropic](https://anthropic.com).
- 🔒 Secure password hashing (Argon2/bcrypt) and JWT authentication.
- 📫 Email-based password recovery and new-account emails (sent in the background).
- 📞 [Traefik](https://traefik.io) reverse proxy with automatic HTTPS.
- ✅ Tests with [Pytest](https://pytest.org) + [Playwright](https://playwright.dev) E2E.
- 🏭 CI/CD with GitHub Actions.

**Frontend — [React](https://react.dev) 19**

- 💃 TypeScript, hooks, [Vite](https://vitejs.dev), [TanStack Router](https://tanstack.com/router)
  and [TanStack Query](https://tanstack.com/query).
- 🎨 [Tailwind CSS](https://tailwindcss.com) v4 + [shadcn/ui](https://ui.shadcn.com) components.
- 🦇 Dark mode / light / system, plus **accent color presets** (Default, Teal, Rose, Amber, Violet).
- 💳 **Billing page** — plan cards, checkout, subscription status, cancel, portal.
- 🤖 **AI Chat page** — token-by-token streaming UI.
- 🔑 **OAuth buttons** on login/signup and a `/auth/callback` token handler.
- 🧩 Built into the backend image and served by FastAPI on the same domain.
- ⚙️ Auto-generated API client (`@hey-api/openapi-ts`).

### Screenshots

[![Dashboard login screenshot](img/login.png)](https://github.com/fastapi/full-stack-fastapi-template)
[![Admin dashboard screenshot](img/dashboard.png)](https://github.com/fastapi/full-stack-fastapi-template)
[![Items dashboard screenshot](img/dashboard-items.png)](https://github.com/fastapi/full-stack-fastapi-template)
[![Dark mode dashboard screenshot](img/dashboard-dark.png)](https://github.com/fastapi/full-stack-fastapi-template)
[![API docs](img/docs.png)](https://github.com/fastapi/full-stack-fastapi-template)

---

## Quick Start

```bash
# 1. Create a copy of the repo
git clone git@github.com:arun3q/full-stack-fastapi-template.git my-app
cd my-app

# 2. Configure (at minimum set SECRET_KEY, FIRST_SUPERUSER_PASSWORD, POSTGRES_PASSWORD)
cp .env .env.local

# 3. Start everything (backend, frontend, Postgres, Redis, worker, Traefik, mailcatcher)
docker compose up -d
```

Open:

- **Application** — <http://localhost>
- **API docs** — <http://localhost/api/v1/docs>
- **Adminer (DB)** — <http://localhost:8080>
- **Mailcatcher** — <http://localhost:1080>

The `prestart` container runs migrations (`alembic upgrade head`) and seeds the
initial superuser and the default plans (Free / Pro / Business / Enterprise).

> **Requires Python 3.14** (stable) for local development. If you only have a
> 3.14 alpha/preview, run everything through Docker (`docker compose up`) which
> uses the stable `python:3.14` image.

---

## How To Use It

### Use as a starting point

**Just fork or clone** this repository and use it as is. ✨ It just works. ✨

### Use with a private repository

GitHub won't allow changing the visibility of forks. Instead:

```bash
git clone git@github.com:fastapi/full-stack-fastapi-template.git my-full-stack
cd my-full-stack
git remote set-url origin git@github.com:octocat/my-full-stack.git
git remote add upstream git@github.com:fastapi/full-stack-fastapi-template.git
git push -u origin master
```

### Update from the original template

Pull the latest upstream changes **without committing** so you can review them:

```bash
git pull --no-commit upstream master
# resolve any conflicts, then:
git merge --continue
```

---

## Configuration

All configuration lives in `.env`. Generate strong values for the defaults with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Core settings (always set these)

| Variable | Description |
| -------- | ----------- |
| `SECRET_KEY` | JWT signing secret. **Change it.** |
| `FIRST_SUPERUSER` | Email of the initial admin (`admin@example.com`). |
| `FIRST_SUPERUSER_PASSWORD` | Password of the initial admin. **Change it.** |
| `POSTGRES_PASSWORD` | Postgres password. **Change it.** |
| `PROJECT_NAME` | Shown to API users. |
| `DOMAIN` | Your public domain (Traefik uses it for routing + TLS). |
| `ENVIRONMENT` | `local` / `staging` / `production`. |
| `FRONTEND_HOST` | Public frontend URL used to build links in emails. |
| `BACKEND_CORS_ORIGINS` | Comma-separated allowed CORS origins. |

### Connection pool tuning

```dotenv
POSTGRES_POOL_SIZE=10
POSTGRES_MAX_OVERFLOW=20
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_PRE_PING=true
```

Tune per worker-process; defaults (10/20) are a good fit for
`fastapi run --workers 4`. See [Performance](#performance--parallelization) below.

### Emails

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_TLS=True
SMTP_USER=...
SMTP_PASSWORD=...
EMAILS_FROM_EMAIL=info@example.com
EMAILS_FROM_NAME=My Project
```

Emails (password recovery, new accounts, test email) are enqueued to the
**worker** and sent asynchronously. In local development use the bundled
[Mailcatcher](https://mailcatcher.me) (see `compose.override.yml`).

### Redis / background jobs

```dotenv
REDIS_URL=redis://localhost:6379/0
```

The job queue runs on a separate **worker** process
(`uv run arq app.worker.WorkerSettings`, or the `worker` Compose service).
If Redis is unavailable, the app keeps working — enqueues fail gracefully and
emails fall back to being sent inline.

### Payments — Stripe

```dotenv
PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...        # fallback price for the "Pro" plan
```

### Payments — Razorpay

```dotenv
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
RAZORPAY_PLAN_ID=plan_...        # fallback plan for the "Pro" plan
```

Point your provider's webhook to `https://<your-domain>/api/v1/payments/webhook`.
Webhooks are signature-verified and processed **idempotently** by the worker.

### Social login / OAuth

Only providers with credentials configured appear on the login page.

```dotenv
OAUTH_CALLBACK_BASE_URL=http://localhost:8000/api/v1
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...
META_CLIENT_ID=...
META_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
```

### AI / LLM

```dotenv
AI_PROVIDER=openai              # or anthropic, or none
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=                # optional: OpenAI-compatible endpoint
OPENAI_MODEL=gpt-4o-mini

ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

### Monitoring

```dotenv
SENTRY_DSN=https://...
```

---

## Feature Deep Dive

### 1. Fully async backend

The request stack is fully asynchronous:

- Endpoints are `async def` and use `SQLModel.AsyncSession` on the `psycopg`
  async driver (no extra driver dependency).
- The async engine is tuned with `pool_pre_ping`, `pool_size` and
  `max_overflow`; the sync engine is kept for Alembic migrations and the
  pre-start scripts, so your migration workflow is unchanged.
- Blocking external SDK calls (Stripe/Razorpay SDKs, SMTP) run in worker threads
  via `asyncio.to_thread`, never blocking the event loop.

Key files:

- `backend/app/core/db.py` — async + sync engines, session factories.
- `backend/app/api/deps.py` — `SessionDep` / `CurrentUser` dependencies.

### 2. Background jobs (ARQ + Redis)

- Queue: [ARQ](https://arq-docs.helpmanual.io) (async, Redis-backed).
- Worker: `backend/app/worker.py` — run with
  `uv run arq app.worker.WorkerSettings` (the `worker` Compose service does this).
- Jobs are defined in `backend/app/core/jobs.py`:
  - `send_email_job` — sends emails off the request path.
  - `process_payment_event_job` — idempotently persists and reconciles provider
    webhook events (updates `Subscription` state).
- Enqueue from anywhere with `await enqueue_job("job_name", ...)`.
- Add your own jobs by defining an async function and registering it in
  `WorkerSettings.functions`.

### 3. Subscriptions & billing (Stripe / Razorpay)

A single `PaymentProvider` interface (`backend/app/core/payments.py`) backs both
providers; the API and frontend are provider-agnostic. Switch with
`PAYMENT_PROVIDER`.

- **Models**: `Plan`, `Subscription`, `PaymentEvent` (see `backend/app/models.py`).
- **Default plans** (Free/Pro/Business/Enterprise) are seeded by
  `backend/app/initial_data.py`. Link each plan to provider pricing through the
  `provider_plan_id` column (Stripe **price id** / Razorpay **plan id**).
- **Webhooks** are signature-verified and handed to the worker for idempotent
  processing, so webhook requests return immediately.
- The frontend **Billing** page lists plans, launches checkout, shows the current
  subscription, and offers cancel + Stripe billing-portal actions.

API endpoints (all under `/api/v1/payments/`):

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/plans` | List active plans |
| POST | `/checkout?plan_id=…` | Create a hosted checkout session → `{id, url}` |
| GET | `/subscription` | Current user's subscription (or `null`) |
| POST | `/subscription/cancel` | Cancel the current subscription |
| POST | `/portal` | Open the Stripe billing portal → `{url}` |
| POST | `/webhook` | Provider webhook (signature verified) |

### 4. Social login / OAuth2

Implemented with [Authlib](https://authlib.org) (`backend/app/core/oauth.py`).

Flow:

1. The login/signup page calls `GET /api/v1/auth/providers` and renders one
   button per **configured** provider.
2. Clicking redirects the user to `GET /api/v1/auth/{provider}` → the provider's
   authorization page.
3. The callback `GET /api/v1/auth/{provider}/callback` exchanges the code, gets
   the profile, then **creates or links** the user:
   - If the `oauth_account` exists → log them in.
   - Else if an account with that email exists → link the provider.
   - Else create a new user (`hashed_password` stays `NULL` for OAuth-only users).
4. The user is redirected to `{FRONTEND_HOST}/auth/callback?token=<jwt>`; the
   frontend stores the token and logs the user in.

### 5. AI / LLM streaming (SSE)

`backend/app/core/ai.py` defines an `AIProvider` abstraction with two
implementations: `OpenAIProvider` (any OpenAI-compatible API) and
`AnthropicProvider`. Responses stream as Server-Sent Events.

API endpoints (all under `/api/v1/ai/`):

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Diagnostics: configured provider + model |
| POST | `/chat` | Stream a completion as `text/event-stream` |

Request body:

```json
{
  "messages": [{ "role": "user", "content": "Hello!" }],
  "system_prompt": "You are a helpful assistant."
}
```

The stream emits `data: {"token": "…"}` events and a final
`data: {"event": "done"}` event. The frontend **AI Chat** page (sidebar → *AI
Chat*) demonstrates a full streaming client with abort/stop support.

### 6. Themeable UI

- Dark / light / system mode.
- Five **accent presets** (Default, Teal, Rose, Amber, Violet) selectable from
  the *Appearance* menu.
- Accents are CSS-variable overrides keyed by `data-accent` on `<html>`
  (`frontend/src/index.css`). To add a brand color, add a few oklch values —
  no component changes needed.

---

## User Types & Access Control

### Roles

Each `User` carries a `role` (`user` | `staff` | `admin`) in addition to the
legacy `is_superuser` flag. The hierarchy is:

| Role | Description | Access |
| ---- | ----------- | ------ |
| `user` | Default account (signup or OAuth) | Own items, profile, billing, AI (if plan allows) |
| `staff` | Moderator / operator | Everything `user` can, plus **all items** (`GET /items/all`) |
| `admin` / `superuser` | Administrator | Everything, plus user management and `test-email` |

Admins and superusers always pass every role/plan check.

### Plan tiers (billing)

| Plan | Access |
| ---- | ------ |
| `free` | Base features, **limited to 5 items** (when billing is enabled) |
| `pro` | Unlimited items + **AI chat** |
| `business` | Everything in Pro + unlimited items (already in Pro) |
| `enterprise` | Everything |

When `PAYMENT_PROVIDER=none` (the default) **all gates are disabled** and every
authenticated user gets full access — so a fresh install "just works".

### Feature flags

`GET /api/v1/users/me/access` returns the resolved access for the current user:

```json
{
  "role": "user",
  "is_superuser": false,
  "is_verified": true,
  "plan": { "slug": "pro", "name": "Pro", "amount_cents": 1999, "currency": "usd", "billing_interval": "month" },
  "features": ["ai:chat", "billing", "items:create", "items:read", "items:unlimited"]
}
```

Available feature flags:

| Flag | Meaning |
| ---- | ------- |
| `items:create` / `items:read` | Base item access |
| `items:unlimited` | No free-plan item limit |
| `ai:chat` | AI chat unlocked |
| `billing` | Billing / subscriptions |
| `staff` / `admin` | Role capabilities |

### Dependencies

Reusable permission dependencies in `backend/app/api/deps.py`:

```python
# staff+ (admins pass)
dependencies=[Depends(require_roles("staff"))]

# any paid plan
dependencies=[Depends(require_plan("pro", "business", "enterprise"))]
```

- `require_roles("staff")` — caller must be `staff` (admins/superusers pass).
- `require_plan("pro", ...)` — caller must hold an **active** subscription to one
  of the given plan slugs; admins/staff pass; disabled when billing is off.

### How gates are wired

| Endpoint | Gate |
| -------- | ---- |
| `GET /items/` | Staff+ see all items; others see their own |
| `GET /items/all` | `require_roles("staff")` |
| `POST /items/` | Free-plan quota (5 items) when billing is enabled |
| `POST /ai/chat` | `require_plan("pro", "business", "enterprise")` |
| `/users/*` admin routes | `get_current_active_superuser` (admin role or superuser) |

### Email verification

Users carry an `is_verified` flag. OAuth-created users are verified automatically
(the provider confirms the email). Admins can set `is_verified` and `role` when
creating/updating users. Extend it with a self-serve email-verification flow by
reusing the existing password-reset token machinery.

---

## Organizations & Multi-tenancy

Every resource in the app is scoped to an **organization** (tenant).

### How it works

- Every user gets a **personal organization** automatically on signup
  (`crud.create_user`), so nothing is blocked out of the box.
- `Organization` + `OrganizationMember` (role: `owner`/`admin`/`member`/`viewer`)
  model the tenancy; `OrganizationInvite` powers email invitations.
- The **active tenant** is resolved by the `X-Organization-ID` header
  (`CurrentOrg` dependency in `api/deps.py`); when absent it falls back to the
  user's most recent membership (their personal org).
- Items and subscriptions are tenant-scoped (`organization_id`), so data is
  isolated between organizations.

### Per-tenant permissions

A permission registry in `core/orgs.py` maps each role to permissions:

| Permission | Owner | Admin | Member | Viewer |
| ---------- | :---: | :---: | :----: | :----: |
| `org:view` | ✓ | ✓ | ✓ | ✓ |
| `org:update` | ✓ | ✓ | | |
| `org:delete` | ✓ | | | |
| `member:invite` | ✓ | ✓ | | |
| `member:manage` | ✓ | ✓ | | |
| `member:remove` | ✓ | | | |
| `billing:manage` | ✓ | ✓ | | |
| `item:create` / `item:read` / `item:update` | ✓ | ✓ | ✓ | |
| `item:read` (viewer) | | | | ✓ |
| `item:delete` | ✓ | ✓ | | |

Enforce with the `require_org_permission("member:invite")` dependency.

### Invitations

An admin can invite a user by email (`POST /organizations/{id}/members`); the
invitee receives an email linking to `/invite?token=...`, and accepts it from
their (logged-in) account. Seat quotas from the plan (`max_seats`) are enforced
when billing is enabled.

### API endpoints (all under `/api/v1/organizations/`)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/` | My organizations |
| POST | `/` | Create organization |
| GET | `/{id}` | Organization detail (members) |
| PATCH | `/{id}` | Update organization (admin+) |
| GET | `/{id}/members` | List members |
| POST | `/{id}/members` | Invite by email (admin+) |
| GET | `/{id}/invites` | List pending invites |
| PATCH | `/{id}/members/{user_id}?role=` | Change role (admin/owner) |
| DELETE | `/{id}/members/{user_id}` | Remove member (owner) |
| POST | `/invites/{token}/accept` | Accept an invitation |

### Frontend

- **Org switcher** in the sidebar (switch active org, create new orgs).
- **Members** page — invite by email, manage roles, remove members, view invites.
- Billing and items are org-scoped automatically.

---

## Enterprise Hardening (Phase 2)

Production-grade security, observability and integrations, all optional:

| Feature | Notes | Settings |
| ------- | ----- | -------- |
| **Refresh tokens + sessions** | `POST /auth/refresh` rotates; `POST /auth/logout` revokes; `GET/DELETE /auth/sessions` manage sessions | `REFRESH_TOKEN_EXPIRE_DAYS` |
| **Rate limiting** | `slowapi` on login/password-recovery | `RATE_LIMIT_STORAGE` (default in-memory) |
| **Failed-login lockout** | Redis counter → 429 after N failures | `LOGIN_FAILURE_LIMIT`, `LOGIN_FAILURE_WINDOW_SECONDS` |
| **TOTP 2FA** | `POST /auth/totp/setup|enable|disable`; login requires a code when enabled | — |
| **Audit log** | `auditlog` table; wired into auth/admin/org/file actions; `GET /admin/audit-log` | — |
| **Structured logs** | JSON logs + `X-Request-ID` correlation | `LOG_FORMAT=json` |
| **Idempotency** | `Idempotency-Key` header replay on POST/PUT/PATCH (Redis) | — |
| **Outbound webhooks** | signed (HMAC), retries + backoff, delivery log, test dispatch | `/api/v1/webhooks/*` |
| **API keys** | hashed, scoped, `X-API-Key` auth | `/api/v1/api-keys/*` |
| **Cron jobs** | expired invites/sessions cleanup, subscription dunning (ARQ) | — |
| **Caching** | plans + public config cached in Redis | `REDIS_URL` |
| **Keyset pagination** | `cursor`/`next_cursor` on `GET /items` | — |
| **Metrics** | Prometheus at `/metrics` | `ENABLE_METRICS` |
| **Object storage** | S3/MinIO uploads via `/api/v1/files/upload` | `S3_*` settings |
| **Cookie auth** | optional httpOnly `access_token` cookie | `AUTH_TOKEN_IN_COOKIE` |

### Admin API (superuser)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/v1/admin/overview` | Platform counters |
| GET | `/api/v1/admin/organizations` | Tenants + member counts |
| GET | `/api/v1/admin/users` | All users |
| PATCH | `/api/v1/admin/users/{id}/status?is_active=` | Enable/disable a user |
| GET | `/api/v1/admin/audit-log` | Recent audit entries |

### Notifications

`GET /api/v1/notifications/`, `/unread-count`, `/{id}/read`, `/read-all` power the
in-app notification bell. An invite acceptance notifies the inviter.

### Scale & compliance notes (Phase 3)

See **`ops.md`** for: backups/PITR runbook, PgBouncer + read replicas,
Row-Level Security (opt-in), enterprise SSO/SCIM, i18n, and monitoring.

---

## API Reference

Interactive API docs are available at `/api/v1/docs` (Swagger UI) and
`/api/v1/openapi.json`.

### Auth & users

| Method | Path | Description |
| ------ | ---- | ----------- |
| POST | `/api/v1/login/access-token` | Email/password login → JWT |
| POST | `/api/v1/login/test-token` | Validate the current token |
| POST | `/api/v1/users/signup` | Public registration |
| GET/PATCH/DELETE | `/api/v1/users/me` | Current user |
| GET | `/api/v1/users/me/access` | Current user's role, plan & feature flags |
| GET/POST/PATCH/DELETE | `/api/v1/users/` | Admin user management |
| POST | `/api/v1/password-recovery/{email}` | Send reset email |
| POST | `/api/v1/reset-password/` | Reset password with token |
| GET | `/api/v1/auth/providers` | List configured OAuth providers |
| GET | `/api/v1/auth/{provider}` | Start OAuth login |
| GET | `/api/v1/auth/{provider}/callback` | OAuth callback |

### Items (example CRUD)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/v1/items/` | List items (owner-scoped; staff+ see all) |
| GET | `/api/v1/items/all` | List all items (staff+ only) |
| POST | `/api/v1/items/` | Create item (free plan limited to 5 when billing is on) |
| GET | `/api/v1/items/{id}` | Get item |
| PUT | `/api/v1/items/{id}` | Update item |
| DELETE | `/api/v1/items/{id}` | Delete item |

### Utils

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/v1/utils/health-check/` | Health check |
| POST | `/api/v1/utils/test-email/` | Send a test email (admin) |

---

## Performance & Parallelization

How the template handles performance today, and how to take it further:

- **Async everywhere**: all endpoints are `async def`; IO-bound work (DB, HTTP,
  SMTP) no longer blocks a thread.
- **Connection pooling**: tuned per-process pool (`POSTGRES_POOL_SIZE`,
  `POSTGRES_MAX_OVERFLOW`). For high concurrency also run
  [PgBouncer](https://www.pgbouncer.org) in front of Postgres.
- **Background jobs**: emails and webhook processing run on the worker, keeping
  request latency low.
- **Multiple workers**: production runs `fastapi run --workers 4`; scale the
  number of replicas as needed.
- **Suggested next steps** for heavy loads:
  - Add a Redis cache layer for hot reads (plans, profiles).
  - Move `COUNT(*)` list queries to windowed/keyset pagination.
  - Add read replicas for reporting queries.

---

## Project Structure

```text
backend/
  app/
    alembic/          # Migrations
    api/
      deps.py         # Dependencies (SessionDep, CurrentUser)
      routes/         # login, users, items, auth, payments, ai, utils, private
    core/
      ai.py           # LLM providers (OpenAI-compatible + Anthropic)
      config.py       # Settings (.env)
      db.py           # Async + sync engines, tuned pool
      jobs.py         # ARQ job definitions + enqueue helper
      oauth.py        # Authlib OAuth registry
      payments.py     # Stripe + Razorpay PaymentProvider
      redis.py        # Shared async Redis client
      security.py     # Password hashing, JWT
    models.py         # SQLModel models (User, Item, OAuthAccount, Plan, Subscription, PaymentEvent)
    worker.py         # ARQ worker entrypoint
    main.py           # FastAPI app + lifespan (Redis pool)
  tests/              # Pytest suite (async)
frontend/
  src/
    components/       # shadcn/ui + feature components (OAuthButtons, …)
    lib/featureApi.ts # Typed client for the new feature endpoints
    routes/           # login, signup, billing, chat, auth/callback, …
compose.yml           # db, redis, worker, backend, adminer, prestart (+ proxy in override)
```

---

## Development

### Backend

```console
cd backend
uv sync
source .venv/bin/activate
```

Run the app locally:

```console
uv run fastapi run app/main.py --reload
```

Run the tests (requires a running Postgres):

```console
uv run bash scripts/prestart.sh   # migrate + seed
uv run pytest
```

Lint / type-check (from the repo root, as CI does):

```console
uv run ruff check backend/app backend/tests
uv run ruff format --check backend/app backend/tests
uv run mypy backend/app
uv run ty check backend/app
```

### Frontend

```console
cd frontend
bun install
bun run dev
```

Build (outputs into `backend/app/frontend`, served by FastAPI):

```console
bun run build
```

Regenerate the API client after changing backend routes:

```console
bun run generate-client
```

### Docker Compose (development)

`compose.override.yml` adds a Traefik proxy, mailcatcher, live-reload for the
backend (`fastapi run --reload`), and a Playwright container. Use:

```console
docker compose watch
```

### Docker Compose (production)

`compose.yml` runs Postgres, Redis, the ARQ worker, and the backend behind
Traefik. See [deployment.md](./deployment.md) for the full deployment guide
(domains, HTTPS via Let's Encrypt, etc.).

---

## Generate Secret Keys

Some `.env` values default to `changethis`. Generate replacements:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## License

The Full Stack FastAPI Template is licensed under the terms of the MIT license.

---

## Related Docs

- [enterprise-features.md](./enterprise-features.md) — condensed configuration reference.
- [backend/README.md](./backend/README.md) — backend development docs.
- [frontend/README.md](./frontend/README.md) — frontend development docs.
- [deployment.md](./deployment.md) — deployment instructions.
- [development.md](./development.md) — general development docs.
- [release-notes.md](./release-notes.md) — release notes.
