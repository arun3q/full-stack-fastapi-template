"""Audit logging: a durable record of who did what, when."""

import json
import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_session_factory
from app.models import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    user_id: Any = None,
    organization_id: Any = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    ip_address: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append an audit entry to the current transaction."""
    session.add(
        AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            detail=json.dumps(detail, default=str) if detail else None,
        )
    )


async def audit_event(
    *,
    action: str,
    user_id: Any = None,
    organization_id: Any = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    ip_address: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Record an audit entry in its own transaction (auth events, etc.)."""
    try:
        async with async_session_factory() as session:
            await record_audit(
                session,
                action=action,
                user_id=user_id,
                organization_id=organization_id,
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=ip_address,
                detail=detail,
            )
            await session.commit()
    except Exception:
        logger.exception("Failed to write audit event: %s", action)
