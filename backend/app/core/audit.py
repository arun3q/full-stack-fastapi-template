"""Audit logging facade.

Persistence lives in ``app.crud.audit``; this module adds a standalone
``audit_event`` that writes in its own transaction (for auth events that happen
outside a request session).
"""

import logging
from typing import Any

from app.core.db import async_session_factory
from app.crud.audit import record_audit  # noqa: F401  (re-export)

logger = logging.getLogger(__name__)


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
