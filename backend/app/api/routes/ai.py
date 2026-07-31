import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import (
    CurrentOrg,
    CurrentUser,
    SessionDep,
    require_plan,
)
from app.core.access import AI_PLANS, billing_enabled, get_active_plan, is_staff
from app.core.ai import get_ai_provider
from app.core.usage import check_quota, record_usage
from app.models import ChatRequest

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/health")
async def ai_health() -> dict[str, Any]:
    """Return the configured AI provider diagnostics."""
    provider = get_ai_provider()
    if provider is None:
        return {"provider": None, "configured": False}
    return await provider.health()


@router.post(
    "/chat",
    dependencies=[Depends(require_plan(*AI_PLANS))],
)
async def chat_stream(
    body: ChatRequest,
    session: SessionDep,
    current_org: CurrentOrg,
    _current_user: CurrentUser,
) -> StreamingResponse:
    """
    Stream a chat completion as Server-Sent Events.

    Each event is ``data: {json}\n\n`` with ``{"token": "..."}`` deltas and a
    final ``{"event": "done"}`` event. AI calls are metered against the org's
    plan quota (``ai_calls``).
    """
    provider = get_ai_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="No AI provider configured")

    # Metered quota check (only when billing is configured)
    if billing_enabled() and not is_staff(_current_user):
        plan = await get_active_plan(session, current_org.id)
        if not await check_quota(
            session,
            organization_id=current_org.id,
            meter="ai_calls",
            amount=1,
            plan=plan,
        ):
            raise HTTPException(
                status_code=429, detail="AI usage quota exceeded for your plan"
            )

    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def event_generator() -> AsyncIterator[str]:
        yield 'data: {"event": "start"}\n\n'
        try:
            async for token in provider.stream_chat(
                messages=messages, system_prompt=body.system_prompt
            ):
                payload = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception:
            yield 'data: {"event": "error", "message": "Stream failed"}\n\n'
            return
        # Record metered usage for the completed call (fresh session: the
        # request-scoped session may already be torn down during streaming)
        from app.core.db import async_session_factory

        async with async_session_factory() as meter_session:
            await record_usage(
                meter_session,
                organization_id=current_org.id,
                meter="ai_calls",
                amount=1,
            )
            await meter_session.commit()
        yield 'data: {"event": "done"}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
