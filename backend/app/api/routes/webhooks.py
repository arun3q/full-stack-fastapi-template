import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, select

from app.api.deps import (
    CurrentOrg,
    SessionDep,
    require_org_permission,
)
from app.core.webhooks import dispatch_webhooks
from app.models import (
    Message,
    Webhook,
    WebhookCreate,
    WebhookDeliveriesPublic,
    WebhookDelivery,
    WebhookDeliveryPublic,
    WebhookPublic,
    WebhooksPublic,
    WebhookUpdate,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get(
    "/",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=WebhooksPublic,
)
async def read_webhooks(session: SessionDep, current_org: CurrentOrg) -> Any:
    webhooks = (
        await session.exec(
            select(Webhook)
            .where(Webhook.organization_id == current_org.id)
            .order_by(col(Webhook.created_at).desc())
        )
    ).all()
    data = [_to_public(w) for w in webhooks]
    return {"data": data, "count": len(data)}


@router.post(
    "/",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=WebhookPublic,
)
async def create_webhook(
    *, session: SessionDep, current_org: CurrentOrg, body: WebhookCreate
) -> Any:
    import secrets

    webhook = Webhook(
        organization_id=current_org.id,
        url=body.url,
        secret=body.secret or secrets.token_urlsafe(24),
        events=json.dumps(body.events or ["*"]),
    )
    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)
    return _to_public(webhook)


@router.get(
    "/{webhook_id}",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=WebhookPublic,
)
async def read_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Any:
    webhook = await _get_webhook(session, current_org, webhook_id)
    return _to_public(webhook)


@router.patch(
    "/{webhook_id}",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=WebhookPublic,
)
async def update_webhook(
    *,
    session: SessionDep,
    current_org: CurrentOrg,
    webhook_id: Any,
    body: WebhookUpdate,
) -> Any:
    webhook = await _get_webhook(session, current_org, webhook_id)
    if body.url is not None:
        webhook.url = body.url
    if body.is_active is not None:
        webhook.is_active = body.is_active
    if body.events is not None:
        webhook.events = json.dumps(body.events)
    session.add(webhook)
    await session.commit()
    await session.refresh(webhook)
    return _to_public(webhook)


@router.delete(
    "/{webhook_id}",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=Message,
)
async def delete_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Message:
    webhook = await _get_webhook(session, current_org, webhook_id)
    await session.delete(webhook)
    await session.commit()
    return Message(message="Webhook deleted")


@router.post(
    "/{webhook_id}/test",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=Message,
)
async def test_webhook(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Message:
    webhook = await _get_webhook(session, current_org, webhook_id)
    await dispatch_webhooks(
        session,
        organization_id=current_org.id,
        event="webhook.test",
        payload={"webhook_id": str(webhook.id), "message": "Test event"},
    )
    await session.commit()
    return Message(message="Test event queued")


@router.get(
    "/{webhook_id}/deliveries",
    dependencies=[Depends(require_org_permission("billing:manage"))],
    response_model=WebhookDeliveriesPublic,
)
async def read_deliveries(
    session: SessionDep, current_org: CurrentOrg, webhook_id: Any
) -> Any:
    await _get_webhook(session, current_org, webhook_id)
    deliveries = (
        await session.exec(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(col(WebhookDelivery.created_at).desc())
            .limit(50)
        )
    ).all()
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
    webhook = await session.get(Webhook, wh_uuid)
    if webhook is None or webhook.organization_id != current_org.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


def _to_public(webhook: Webhook) -> WebhookPublic:
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
