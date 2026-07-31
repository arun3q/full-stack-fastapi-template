"""Background job queue based on ARQ (backed by Redis).

Jobs are enqueued from request handlers and executed by a separate worker
process (see ``app/worker.py``). If Redis is unavailable the application keeps
working: enqueues fail gracefully and e.g. emails are sent inline as a fallback.
"""

from app.core.jobs.base import (
    create_redis_pool,
    enqueue_job,
    get_redis_pool,
    get_utc_now,
    redis_settings,
    set_redis_pool,
)
from app.core.jobs.emails import send_email_background, send_email_job
from app.core.jobs.maintenance import (
    cleanup_expired_invites_job,
    cleanup_revoked_sessions_job,
    subscription_dunning_job,
)
from app.core.jobs.payments import process_payment_event_job
from app.core.jobs.webhooks import (
    MAX_WEBHOOK_ATTEMPTS,
    WEBHOOK_BACKOFF_SECONDS,
    deliver_webhook_job,
)

__all__ = [
    "create_redis_pool",
    "enqueue_job",
    "get_redis_pool",
    "get_utc_now",
    "redis_settings",
    "set_redis_pool",
    "send_email_background",
    "send_email_job",
    "cleanup_expired_invites_job",
    "cleanup_revoked_sessions_job",
    "subscription_dunning_job",
    "process_payment_event_job",
    "deliver_webhook_job",
    "MAX_WEBHOOK_ATTEMPTS",
    "WEBHOOK_BACKOFF_SECONDS",
]
