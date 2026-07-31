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

**Read replicas** — add a replica and expose a second engine for read-only
queries. A ready-made pattern: add `READ_REPLICA_URL` to settings and a
`get_read_session` dependency that routes `SELECT`-only endpoints (reporting,
list endpoints) to the replica engine. Kept out of the core template to avoid
over-configuring; wire it when you need it.

---

## Row-Level Security (RLS, optional hardening)

The app already scopes every query by `organization_id`. RLS is an optional
defense-in-depth layer at the database.

**Enable it (opt-in):**

1. Enable RLS on the tenant tables:

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

2. Set the tenant on every transaction. In `app/core/db.py`, extend
   `get_async_session()` to run:

```sql
SELECT set_config('app.current_org_id', :org, true);
SELECT set_config('app.is_admin', :admin, true);
```

   using the resolved `X-Organization-ID` header and the user's admin status.

> Because the app-level queries already filter by `organization_id`, RLS is a
> second line of defense, not the primary isolation mechanism. Enable it after
> load-testing your write paths.

---

## Enterprise SSO & SCIM

- **SSO (SAML / OIDC):** Authlib already powers OIDC social login. For
  enterprise SAML, integrate [python3-saml](https://github.com/onelogin/python3-saml)
  behind the same `/auth/{provider}/callback` pattern. Add a `Provider` config
  (idp metadata, cert) per tenant and require it for SSO-forced organizations.
- **SCIM provisioning:** expose the SCIM 2.0 endpoints
  (`/scim/v2/Users`, `/scim/v2/Groups`) authenticated with a tenant bearer
  token; map create/update/deactivate to `OrganizationMember` + `User` lifecycle.
- **Session/SSO account linking:** reuse `OAuthAccount` (`provider`,
  `provider_account_id`) to link enterprise identities to users.

---

## i18n (internationalization)

The frontend is English-only today. To add i18n:

1. Add `i18next` + `react-i18next` and wrap the app.
2. Replace hardcoded strings with `t("key")` and ship `locales/en/*.json`
   (and additional locales).
3. Add a `LANGUAGE` setting; persist the choice with the theme.

Backend: Pydantic validation errors can be localized with a custom
`RequestValidationError` handler mapping error messages per locale.

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
