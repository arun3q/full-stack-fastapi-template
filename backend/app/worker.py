"""Background worker entrypoint.

Run with:  ``uv run arq app.worker.WorkerSettings``
"""

import asyncio
import logging
from typing import Any, cast

from arq.connections import RedisSettings
from arq.cron import cron
from arq.worker import create_worker

from app.core.jobs import (
    cleanup_expired_invites_job,
    cleanup_revoked_sessions_job,
    deliver_webhook_job,
    process_payment_event_job,
    redis_settings,
    requeue_stale_webhook_deliveries_job,
    send_email_job,
    subscription_dunning_job,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def startup(_ctx: dict[str, Any]) -> None:
    from app.core.config import settings
    from app.core.telemetry import init_telemetry

    init_telemetry()
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(
            dsn=str(settings.SENTRY_DSN),
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1,
        )
        logger.info("Worker Sentry enabled")
    logger.info("Worker started")


async def shutdown(_ctx: dict[str, Any]) -> None:
    logger.info("Worker stopped")


class WorkerSettings:
    """Settings understood by the ARQ worker."""

    functions = [
        send_email_job,
        process_payment_event_job,
        deliver_webhook_job,
        cleanup_expired_invites_job,
        cleanup_revoked_sessions_job,
        subscription_dunning_job,
    ]
    cron_jobs: list[Any] = [
        cron(cast(Any, cleanup_expired_invites_job), hour=3, minute=0),
        cron(cast(Any, cleanup_revoked_sessions_job), hour=4, minute=0),
        cron(cast(Any, subscription_dunning_job), hour=9, minute=0),
        cron(cast(Any, requeue_stale_webhook_deliveries_job), minute=15),
    ]
    redis_settings: RedisSettings = redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
    retry_jobs = True
    max_tries = 3
    job_retry_seconds = 30


async def _run() -> None:
    worker = create_worker(cast(Any, WorkerSettings))
    await worker.run()  # type: ignore


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
