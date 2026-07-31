import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    CurrentOrg,
    CurrentUser,
    SessionDep,
    require_org_permission,
    require_roles,
)
from app.core.access import (
    billing_enabled,
    get_active_plan,
    is_staff,
    plan_quota,
)
from app.crud.items import count_items, get_item, list_items
from app.crud.items import create_item as create_item_crud
from app.models import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

router = APIRouter(prefix="/items", tags=["items"])

FREE_PLAN_MAX_ITEMS = 5


@router.get("/", response_model=ItemsPublic)
async def read_items(
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    skip: int = 0,
    limit: int = 100,
    cursor: str | None = None,
) -> Any:
    """
    Retrieve items. Staff+ see every item; everyone else sees their
    organization's items. Supports keyset pagination via ``cursor``.
    """
    try:
        if is_staff(current_user):
            count = await count_items(session)
            items, next_cursor = await list_items(
                session=session, skip=skip, limit=limit
            )
        else:
            count = await count_items(session, current_org.id)
            items, next_cursor = await list_items(
                session=session,
                organization_id=current_org.id,
                skip=skip,
                limit=limit,
                cursor=cursor,
            )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")

    items_public = [ItemPublic.model_validate(item) for item in items]
    return ItemsPublic(data=items_public, count=count, next_cursor=next_cursor)


@router.get(
    "/all",
    dependencies=[Depends(require_roles("staff"))],
    response_model=ItemsPublic,
)
async def read_all_items(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """List every item in the system (staff or above only)."""
    count = await count_items(session)
    items, _ = await list_items(session=session, skip=skip, limit=limit)
    items_public = [ItemPublic.model_validate(item) for item in items]
    return ItemsPublic(data=items_public, count=count)


@router.get("/{id}", response_model=ItemPublic)
async def read_item(
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    id: uuid.UUID,
) -> Any:
    """
    Get item by ID.
    """
    item = await get_item(session, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not is_staff(current_user) and item.organization_id != current_org.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item


@router.post(
    "/",
    dependencies=[Depends(require_org_permission("item:create"))],
    response_model=ItemPublic,
)
async def create_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    item_in: ItemCreate,
) -> Any:
    """
    Create new item in the active organization.
    """
    # Plan-driven item quota (only enforced when a payment provider is configured)
    if billing_enabled() and not is_staff(current_user):
        plan = await get_active_plan(session, current_org.id)
        max_items = (
            FREE_PLAN_MAX_ITEMS
            if plan is None
            else plan_quota(plan, "max_items", default=0)
        )
        if max_items > 0:
            count = await count_items(session, current_org.id)
            if count >= max_items:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Your plan is limited to {max_items} items. "
                        "Upgrade your plan for more."
                    ),
                )

    item = await create_item_crud(
        session=session,
        item_in=item_in,
        owner_id=current_user.id,
        organization_id=current_org.id,
    )
    return item


@router.put(
    "/{id}",
    dependencies=[Depends(require_org_permission("item:update"))],
    response_model=ItemPublic,
)
async def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = await get_item(session, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not is_staff(current_user) and item.organization_id != current_org.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.delete(
    "/{id}",
    dependencies=[Depends(require_org_permission("item:delete"))],
)
async def delete_item(
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    id: uuid.UUID,
) -> Message:
    """
    Delete an item.
    """
    item = await get_item(session, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not is_staff(current_user) and item.organization_id != current_org.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    await session.delete(item)
    await session.commit()
    return Message(message="Item deleted successfully")
