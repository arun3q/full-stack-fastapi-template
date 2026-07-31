"""Background worker entrypoint.

Run with:  ``uv run arq app.worker.WorkerSettings``
"""

import asyncio
import logging
from typing import Any, cast

from arq.connections import RedisSettings
from arq.worker import create_worker

from app.core.jobs import process_payment_event_job, redis_settings, send_email_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def startup(_ctx: dict[str, Any]) -> None:
    logger.info("Worker started")


async def shutdown(_ctx: dict[str, Any]) -> None:
    logger.info("Worker stopped")


class WorkerSettings:
    """Settings understood by the ARQ worker."""

    functions = [send_email_job, process_payment_event_job]
    cron_jobs: list[Any] = []
    redis_settings: RedisSettings = redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
    keep_result = 60


async def _run() -> None:
    worker = create_worker(cast(Any, WorkerSettings))
    await worker.run()  # type: ignore


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
