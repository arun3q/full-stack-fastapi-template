# Enterprise Features

This branch extends the base template with the features most SaaS products need
out of the box: **async I/O**, **background jobs**, **subscriptions/billing**,
**social login (OAuth)**, **AI streaming**, and **themeable UI**.

All features are optional. The application works out of the box with everything
disabled and each feature lights up as you add configuration to your `.env`.

---

## 1. Fully async backend + tuned connection pool

- The request stack is now fully async (SQLModel `AsyncSession` on the
  `psycopg` async driver — no extra driver needed).
- The engine is tuned with `pool_pre_ping`, `pool_size` and `max_overflow`.
  Per-process defaults (10 / 20) work well with `fastapi run --workers 4`;
  tune them to your deployment in `.env`:

```dotenv
POSTGRES_POOL_SIZE=10
POSTGRES_MAX_OVERFLOW=20
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_PRE_PING=true
```

- Migration tooling (Alembic) and the pre-start scripts keep using a separate
  synchronous engine, so nothing changes in your migration workflow.

## 2. Background jobs (ARQ + Redis)

Emails and payment webhook processing run on a **separate worker process** so
they never block request handlers. If Redis is unavailable, the app keeps
working: enqueues fail gracefully and emails fall back to being sent inline.

- Job queue: [ARQ](https://arq-docs.helpmanual.io) (async, Redis-backed).
- Add a job by defining an async function in `backend/app/core/jobs.py` and
  registering it in `WorkerSettings.functions` in `backend/app/worker.py`.
- Start the worker: `uv run arq app.worker.WorkerSettings` (the Docker Compose
  `worker` service already runs it).

`.env`:

```dotenv
REDIS_URL=redis://localhost:6379/0
```

## 3. Subscriptions & billing (Stripe or Razorpay)

A single `PaymentProvider` interface (`backend/app/core/payments.py`) backs two
implementations. Everything else (checkout, webhooks, subscription state) is
provider-agnostic. Set `PAYMENT_PROVIDER` to `stripe` or `razorpay`.

The default plans (Free / Pro / Business / Enterprise) are seeded by
`initial_data.py`. Link a plan to its provider pricing via the `provider_plan_id`
column (Stripe price id / Razorpay plan id).

Endpoints (`/api/v1/payments/...`):

| Method | Path                              | Description                              |
| ------ | --------------------------------- | ---------------------------------------- |
| GET    | `/payments/plans`                 | List active plans                        |
| POST   | `/payments/checkout?plan_id=`     | Create a hosted checkout session         |
| GET    | `/payments/subscription`          | Current user's subscription              |
| POST   | `/payments/subscription/cancel`   | Cancel the current subscription          |
| POST   | `/payments/portal`                | Open the Stripe billing portal           |
| POST   | `/payments/webhook`               | Provider webhook (signature-verified)    |

`.env` (Stripe):

```dotenv
PAYMENT_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...   # fallback price for the "Pro" plan
```

`.env` (Razorpay):

```dotenv
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
RAZORPAY_PLAN_ID=plan_...    # fallback plan for the "Pro" plan
```

Configure the webhook URL at your provider to point to
`https://<your-domain>/api/v1/payments/webhook`. Webhooks are signature-verified
and processed idempotently by the worker (`provider_event_id` is unique).

## 4. Social login / OAuth (Authlib)

Providers are registered lazily — only those with credentials configured appear
on the login page (`GET /api/v1/auth/providers`).

Supported providers: **Google**, **LinkedIn**, **Meta (Facebook)**, **GitHub**.

`.env`:

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

Flow: the login page renders a button per configured provider → user is
redirected to the provider → the callback (`/api/v1/auth/{provider}/callback`)
creates/links the user (an `oauth_account` row; the local `hashed_password`
stays `NULL` for OAuth-only accounts) → the user is redirected back to
`/auth/callback?token=<access_token>` on the frontend, which stores the token.

## 5. AI / LLM streaming (SSE)

Provider-agnostic streaming chat (OpenAI-compatible APIs such as OpenAI, Groq,
Ollama, vLLM — and Anthropic). Responses stream as Server-Sent Events so tokens
render as they arrive.

`.env`:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_BASE_URL=             # optional, for OpenAI-compatible endpoints
OPENAI_MODEL=gpt-4o-mini

# or
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

Endpoints:

| Method | Path            | Description                                  |
| ------ | --------------- | -------------------------------------------- |
| GET    | `/api/v1/ai/health` | Provider diagnostics (configured/model)   |
| POST   | `/api/v1/ai/chat`   | Stream a completion as `text/event-stream` |

The frontend ships an AI Chat page (sidebar → *AI Chat*) demonstrating the
streaming client.

## 6. Themeable UI

The frontend exposes both dark/light/system modes and five **accent presets**
(Default, Teal, Rose, Amber, Violet) from the *Appearance* menu. Accents are
implemented as CSS-variable overrides in `frontend/src/index.css`
(`data-accent` attribute on `<html>`), so adding a brand color is a few oklch
values.

## Docker Compose

`compose.yml` gained two services:

- `redis` — the job queue backend.
- `worker` — runs the ARQ worker (same image as the backend).

Start everything with `docker compose up -d`.

## Running the tests

```console
cd backend
uv sync
# a Postgres instance is required (the compose `db` service works)
uv run bash scripts/prestart.sh
uv run pytest
```

Lint/type checks (run from the repo root, as CI does):

```console
uv run ruff check backend/app backend/tests
uv run ruff format --check backend/app backend/tests
uv run mypy backend/app
uv run ty check backend/app
```
