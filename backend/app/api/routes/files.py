import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import (
    CurrentOrg,
    CurrentUser,
    SessionDep,
    require_org_permission,
)
from app.core.access import billing_enabled, get_active_plan, is_staff
from app.core.audit import record_audit
from app.core.storage import StorageError, download_file, upload_file
from app.core.usage import check_quota, record_usage

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/upload",
    dependencies=[Depends(require_org_permission("item:create"))],
    response_model=dict[str, str],
)
async def upload(
    session: SessionDep,
    current_user: CurrentUser,
    current_org: CurrentOrg,
    file: UploadFile = File(...),
) -> Any:
    """Upload a file to S3-compatible storage and return its public URL."""
    content = await file.read()

    # Metered storage quota (only when billing is configured)
    if billing_enabled() and not is_staff(current_user):
        plan = await get_active_plan(session, current_org.id)
        if not await check_quota(
            session,
            organization_id=current_org.id,
            meter="storage_bytes",
            amount=len(content),
            plan=plan,
        ):
            raise HTTPException(
                status_code=413, detail="Storage quota exceeded for your plan"
            )

    try:
        url = await upload_file(
            filename=file.filename or "file",
            content=content,
            content_type=file.content_type or "application/octet-stream",
            organization_id=current_org.id,
        )
    except StorageError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    await record_usage(
        session,
        organization_id=current_org.id,
        meter="storage_bytes",
        amount=len(content),
        user_id=current_user.id,
    )
    await record_audit(
        session,
        action="file.upload",
        user_id=current_user.id,
        organization_id=current_org.id,
        entity_type="file",
        detail={"filename": file.filename, "bytes": len(content)},
    )
    await session.commit()
    return {"url": url}


@router.get(
    "/download/{organization_id}/{file_name}",
    dependencies=[Depends(require_org_permission("item:view"))],
)
async def download(
    current_org: CurrentOrg,
    organization_id: uuid.UUID,
    file_name: str,
    _session: SessionDep,
    _current_user: CurrentUser,
) -> Any:
    """Org-scoped download of an object whose key is namespaced by the org."""
    from fastapi.responses import Response

    if organization_id != current_org.id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    key = f"uploads/{organization_id}/{file_name}"
    try:
        body = await download_file(key=key)
    except StorageError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return Response(content=body, media_type="application/octet-stream")
