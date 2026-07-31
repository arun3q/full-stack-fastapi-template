"""Keyset (cursor) pagination helpers."""

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any


def encode_cursor(created_at: datetime | None, id: Any) -> str | None:
    """Encode a cursor from the sort key (created_at, id)."""
    if created_at is None:
        return None
    payload = json.dumps([created_at.isoformat(), str(id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    """Decode a cursor into ``(created_at, id)`` for keyset filtering."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, list) or len(data) != 2:
            return None
        created_at = datetime.fromisoformat(str(data[0])).astimezone(UTC)
        item_id = uuid.UUID(str(data[1]))
        return created_at, item_id
    except Exception:
        return None
