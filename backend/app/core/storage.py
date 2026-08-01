"""Object storage (S3 / MinIO compatible) uploads."""

import asyncio
import logging
import uuid
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when object storage is not configured or the upload fails."""


def _client() -> Any:
    import boto3

    if not settings.S3_ENDPOINT_URL or not settings.S3_ACCESS_KEY:
        raise StorageError("S3 storage is not configured (S3_ENDPOINT_URL)")
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name="us-east-1",
    )


def _put(client: Any, bucket: str, key: str, body: bytes, content_type: str) -> None:
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


async def upload_file(
    *,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
    organization_id: Any = None,
) -> str:
    client = _client()
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    prefix = f"uploads/{organization_id}" if organization_id else "uploads"
    key = f"{prefix}/{uuid.uuid4().hex}/{safe_name}"
    await asyncio.to_thread(
        _put, client, settings.S3_BUCKET, key, content, content_type
    )
    public_url = settings.S3_PUBLIC_URL
    if public_url:
        return f"{public_url.rstrip('/')}/{key}"
    endpoint = settings.S3_ENDPOINT_URL or ""
    return f"{endpoint.rstrip('/')}/{settings.S3_BUCKET}/{key}"


async def download_file(*, key: str) -> bytes:
    """Fetch an object's bytes (used by the org-scoped download endpoint)."""
    client = _client()
    response = await asyncio.to_thread(_get, client, settings.S3_BUCKET, key)
    return response.get("Body").read()


def _get(client: Any, bucket: str, key: str) -> Any:
    return client.get_object(Bucket=bucket, Key=key)
