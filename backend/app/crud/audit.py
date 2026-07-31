"""Audit log repository."""

import json
from collections.abc import Sequence
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import AuditLog


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


async def list_audit_logs(
    session: AsyncSession, skip: int = 0, limit: int = 100
) -> Sequence[AuditLog]:
    return (
        await session.exec(
            select(AuditLog)
            .order_by(col(AuditLog.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()
