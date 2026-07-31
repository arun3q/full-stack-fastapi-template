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
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    cursor: str | None = None,
) -> tuple[Sequence[AuditLog], str | None]:
    from app.core.pagination import decode_cursor, encode_cursor

    statement = select(AuditLog).order_by(col(AuditLog.created_at).desc()).limit(limit)
    if cursor:
        keyset = decode_cursor(cursor)
        if keyset is None:
            raise ValueError("Invalid cursor")
        cursor_created_at, cursor_id = keyset
        statement = statement.where(
            (col(AuditLog.created_at) < cursor_created_at)
            | (
                (col(AuditLog.created_at) == cursor_created_at)
                & (AuditLog.id < cursor_id)
            )
        )
    else:
        statement = statement.offset(skip)
    entries = (await session.exec(statement)).all()
    next_cursor = (
        encode_cursor(entries[-1].created_at, entries[-1].id)
        if entries and len(entries) == limit
        else None
    )
    return entries, next_cursor
