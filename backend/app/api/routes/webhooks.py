import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    CurrentOrg,
    SessionDep,
    require_org_permission,
)
from app.core.webhooks import dispatch_webhooks
from app.crud.webhooks import (
    create_webhook,
    get_webhook,
    list_deliveries,
    list_webhooks,
    update_webhook,
)
from app.models import (
    Message,
    Webhook,
    WebhookCreate,
    WebhookDeliveriesPublic,
    WebhookDeliveryPublic,
    WebhookPublic,
    WebhooksPublic,
    WebhookUpdate,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_require = Depends(require_org_permission("billing:manage"))


@router.get("/", dependencies=[_require], response_model=WebhooksPublic)
async def read_webhooks(session: SessionDep, current_org: CurrentOrg) -> Any:
    webhooks = await list_webhooks(session, current_org.id)
    data = [_to_public(w) for w in webhooks]
    return {"data": data, "count": len(data)}


@router.post("/", dependencies=[_require], response_model=WebhookPublic)
async def create_webhook_route(
    *, session: SessionDep, current_org: CurrentOrg, body: WebhookCreate
) -> Any:
    webhook = await create_webhook(
        session,
        organization_id=current_org.id,
        url=body.url,
        secret=body.secret or secrets.token_urlsafe(24),
        events=body.events or ["*"],
    )
    await session.commit()
    await session.refresh(webhook)
    return _to_public(webhook)


@router.get("/{webhook_id}", dependencies=[_require], response_model=WebhookPublic)
async def read_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Any:
    webhook = await _get_webhook(session, current_org, webhook_id)
    return _to_public(webhook)


@router.patch("/{webhook_id}", dependencies=[_require], response_model=WebhookPublic)
async def update_webhook_route(
    *,
    session: SessionDep,
    current_org: CurrentOrg,
    webhook_id: Any,
    body: WebhookUpdate,
) -> Any:
    webhook = await _get_webhook(session, current_org, webhook_id)
    webhook = await update_webhook(
        session,
        webhook,
        url=body.url,
        is_active=body.is_active,
        events=body.events,
    )
    await session.commit()
    await session.refresh(webhook)
    return _to_public(webhook)


@router.delete("/{webhook_id}", dependencies=[_require], response_model=Message)
async def delete_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Message:
    webhook = await _get_webhook(session, current_org, webhook_id)
    await session.delete(webhook)
    await session.commit()
    return Message(message="Webhook deleted")


@router.post("/{webhook_id}/test", dependencies=[_require], response_model=Message)
async def test_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Message:
    await _get_webhook(session, current_org, webhook_id)
    await dispatch_webhooks(
        session,
        organization_id=current_org.id,
        event="webhook.test",
        payload={"webhook_id": str(webhook_id), "message": "Test event"},
    )
    await session.commit()
    return Message(message="Test event queued")


@router.get(
    "/{webhook_id}/deliveries",
    dependencies=[_require],
    response_model=WebhookDeliveriesPublic,
)
async def read_deliveries(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Any:
    await _get_webhook(session, current_org, webhook_id)
    deliveries = await list_deliveries(session, webhook_id)
    data = [WebhookDeliveryPublic.model_validate(d) for d in deliveries]
    return {"data": data, "count": len(data)}


async def _get_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Webhook:
    from uuid import UUID

    try:
        wh_uuid = UUID(str(webhook_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Webhook not found")
    webhook = await get_webhook(session, wh_uuid)
    if webhook is None or webhook.organization_id != current_org.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


def _to_public(webhook: Webhook) -> WebhookPublic:
    import json

    try:
        events = json.loads(webhook.events or "[]")
    except Exception:
        events = []
    return WebhookPublic(
        id=webhook.id,
        url=webhook.url,
        events=events if isinstance(events, list) else [],
        is_active=webhook.is_active,
        created_at=webhook.created_at,
    )
