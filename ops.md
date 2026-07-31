# Operations Runbook & Scale Guide

Covers the Phase 3 operational items: backups/PITR, connection pooling,
read replicas, Row-Level Security, enterprise SSO/SCIM, i18n and monitoring.

---

## Backups & Point-in-Time Recovery (PITR)

PostgreSQL supports continuous archiving (WAL) for point-in-time recovery.

**Daily base backup (with `pg_dump`):**

```bash
docker exec <db-container> pg_dump -U postgres -Fc app > backups/app-$(date +%F).dump
```

**WAL archiving for PITR** — run Postgres with archive mode:

```yaml
# compose.prod.yml (db service)
command:
  - "postgres"
  - "-c"
  - "wal_level=replica"
  - "-c"
  - "archive_mode=on"
  - "-c"
  - "archive_command=cp %p /backups/wal/%f"
```

**Restore to a point in time:**

```bash
# 1. restore the base backup
pg_restore -U postgres -d app --clean backups/app-YYYY-MM-DD.dump
# 2. replay WAL up to a target time
pg_ctl start -o "-c recovery_target_time='2026-08-01 12:00:00 UTC'"
```

> Store base dumps off-host (S3) and keep WAL on durable storage. Test restores
> periodically. See the official [PostgreSQL backup docs](https://www.postgresql.org/docs/current/backup.html).

---

## Connection pooling (PgBouncer) & read replicas

For high concurrency, put [PgBouncer](https://www.pgbouncer.org) in front of
Postgres in *transaction* mode:

```yaml
# compose.prod.yml
pgbouncer:
  image: edoburu/pgbouncer
  environment:
    DB_HOST: db
    DB_USER: ${POSTGRES_USER}
    DB_PASSWORD: ${POSTGRES_PASSWORD}
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 1000
  ports: ["6432:5432"]
```

Point the app at PgBouncer (`POSTGRES_SERVER=pgbouncer`, `POSTGRES_PORT=6432`).
The async pool already uses `pool_pre_ping`, which works well behind a pooler.

**Read replicas** — wired in:

```dotenv
READ_REPLICA_URL=postgresql+psycopg://user:pass@replica-host/app
```

When set, the app creates a read-only engine and the `get_read_session`
dependency routes read-heavy endpoints (users, items, admin lists, plans) to it.
When unset it falls back to the primary. Add a replica in Postgres (streaming
replication), then set the URL.

---

## Row-Level Security (RLS, optional hardening)

The app already scopes every query by `organization_id`. RLS is an optional
defense-in-depth layer at the database.

**Enable it:**

1. Set `ENABLE_RLS=true` — the app then runs
   `set_config('app.current_org_id', ...)` and `set_config('app.is_admin', ...)`
   per request (tenant + admin flows).
2. Apply the policies to the tenant tables:

```sql
ALTER TABLE item ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizationmember ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON item
  USING (
    (SELECT current_setting('app.current_org_id', true)) = organization_id::text
    OR (SELECT current_setting('app.is_admin', true)) = 'true'
  );
-- repeat for subscription, organizationmember
```

> Because the app-level queries already filter by `organization_id`, RLS is a
> second line of defense, not the primary isolation mechanism.

---

## Enterprise SSO (SAML) & SCIM

**SAML SSO** — wired with `python3-saml`:

```dotenv
SAML_ENABLED=true
SAML_SP_ENTITY_ID=https://<your-domain>/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=https://<your-domain>/api/v1/auth/saml/acs
SAML_IDP_METADATA=https://idp.example.com/metadata   # file path or URL
SAML_ATTRIBUTE_EMAIL=email
SAML_ATTRIBUTE_NAME=displayname
```

Endpoints:

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/v1/auth/saml/metadata` | SP metadata (register in your IdP) |
| GET | `/api/v1/auth/saml/login` | SP-initiated login → redirect to IdP |
| POST | `/api/v1/auth/saml/acs` | Assertion consumer (provisions the user + session) |
| GET | `/api/v1/auth/saml/status` | `configured` / `not-configured` |

**SCIM 2.0 provisioning** — `python3-saml` not needed; SCIM authenticates with
an organization API key (`Authorization: Bearer <key>` or `X-API-Key`) and
provisions users as members of that key's organization:

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/v1/scim/v2/ServiceProviderConfig` | Capabilities |
| GET | `/api/v1/scim/v2/Users` | List members |
| GET | `/api/v1/scim/v2/Users/{id}` | Get a member |
| POST | `/api/v1/scim/v2/Users` | Provision a user (create + add to org) |
| PATCH | `/api/v1/scim/v2/Users/{id}` | Update (active=false deactivates) |
| DELETE | `/api/v1/scim/v2/Users/{id}` | Deactivate (SCIM delete == deactivate) |
| GET | `/api/v1/scim/v2/Groups` | Role-based groups (owner/admin/member/viewer) |

---

## i18n (internationalization)

Implemented with `i18next` + `react-i18next`:

- Locales live in `frontend/src/i18n/locales/{en,es}.json` (add more by adding a
  JSON file and registering it in `frontend/src/i18n/index.ts`).
- The *Appearance* menu includes a **Language** switcher (English/Español).
- Key surfaces are translated (marketing, auth, app shell, dashboard, appearance);
  add strings as you build out the app.
- Backend: Pydantic validation errors can be localized with a custom
  `RequestValidationError` handler mapping messages per locale.

---

## Monitoring

- `/metrics` exposes Prometheus metrics (requests, latency).
- Scrape with Prometheus and visualize in Grafana.
- Sentry captures errors (configure `SENTRY_DSN`).
- Structured logs (`LOG_FORMAT=json`) include `request_id` for correlation.

```yaml
# docker-compose.prod.yml (Prometheus)
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports: ["9090:9090"]
```

---

## Deploy / rollback checklist

- [ ] Run migrations (`alembic upgrade head`) via the `prestart` job before the app starts.
- [ ] Health-check `GET /api/v1/utils/health-check/` behind the load balancer.
- [ ] Verify the `worker` service is up (`uv run arq app.worker.WorkerSettings`).
- [ ] Verify Redis connectivity (jobs + rate limiting + cache).
- [ ] On rollback: redeploy the previous image; run `alembic downgrade` only if
      the last migration is safe to reverse, otherwise migrate forward.
