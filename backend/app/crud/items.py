"""Item repository."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.models import Item, ItemCreate


async def create_item(
    *,
    session: AsyncSession,
    item_in: ItemCreate,
    owner_id: uuid.UUID,
    organization_id: uuid.UUID | None = None,
) -> Item:
    db_item = Item.model_validate(
        item_in,
        update={"owner_id": owner_id, "organization_id": organization_id},
    )
    session.add(db_item)
    await session.commit()
    await session.refresh(db_item)
    return db_item


async def get_item(session: AsyncSession, item_id: uuid.UUID) -> Item | None:
    return await session.get(Item, item_id)


async def count_items(session: AsyncSession, organization_id: Any | None = None) -> int:
    statement = select(func.count()).select_from(Item)
    if organization_id is not None:
        statement = statement.where(Item.organization_id == organization_id)
    return (await session.exec(statement)).one()


async def list_items(
    *,
    session: AsyncSession,
    organization_id: Any | None = None,
    skip: int = 0,
    limit: int = 100,
    cursor: str | None = None,
) -> tuple[Sequence[Item], str | None]:
    """Return ``(items, next_cursor)`` with optional keyset pagination."""
    statement = select(Item).order_by(col(Item.created_at).desc()).limit(limit)
    if organization_id is not None:
        statement = statement.where(Item.organization_id == organization_id)
    if cursor:
        keyset = decode_cursor(cursor)
        if keyset is None:
            raise ValueError("Invalid cursor")
        cursor_created_at, cursor_id = keyset
        statement = statement.where(
            (col(Item.created_at) < cursor_created_at)
            | ((col(Item.created_at) == cursor_created_at) & (Item.id < cursor_id))
        )
    else:
        statement = statement.offset(skip)
    items = (await session.exec(statement)).all()
    next_cursor = (
        encode_cursor(items[-1].created_at, items[-1].id)
        if items and len(items) == limit
        else None
    )
    return items, next_cursor
