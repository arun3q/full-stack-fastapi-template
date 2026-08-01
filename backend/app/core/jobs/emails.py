"""Email jobs: send email off the request path."""

import asyncio
from typing import Any

from app.core.config import settings
from app.core.jobs.base import enqueue_job
from app.utils import send_email


async def send_email_job(
    _ctx: dict[str, Any],
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    """Send an email outside of the request/response cycle."""
    await asyncio.to_thread(
        send_email, email_to=email_to, subject=subject, html_content=html_content
    )


async def send_email_background(
    *, email_to: str, subject: str = "", html_content: str = ""
) -> None:
    """Enqueue an email, falling back to sending it inline if no worker is up."""
    job_id = await enqueue_job(
        "send_email_job",
        email_to=email_to,
        subject=subject,
        html_content=html_content,
    )
    if job_id is None and settings.emails_enabled:
        # Keep SMTP off the event loop in the inline fallback path too
        await asyncio.to_thread(
            send_email, email_to=email_to, subject=subject, html_content=html_content
        )
