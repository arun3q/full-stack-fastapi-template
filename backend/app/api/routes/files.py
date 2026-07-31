from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import (
    CurrentOrg,
    CurrentUser,
    SessionDep,
    require_org_permission,
)
from app.core.audit import record_audit
from app.core.storage import StorageError, upload_file

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
    try:
        url = await upload_file(
            filename=file.filename or "file",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except StorageError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    await record_audit(
        session,
        action="file.upload",
        user_id=current_user.id,
        organization_id=current_org.id,
        entity_type="file",
        detail={"filename": file.filename},
    )
    await session.commit()
    return {"url": url}
