"""MinIO object-storage client wrapper."""

import io
from datetime import timedelta

import structlog
from minio import Minio

from durgam.config import settings

log = structlog.get_logger(__name__)

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def upload_file(storage_key: str, data: bytes, content_type: str) -> None:
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.minio_bucket,
        object_name=storage_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    log.info("file_uploaded", storage_key=storage_key, size=len(data))


def get_presigned_url(storage_key: str, expires_in: int = 3600) -> str:
    client = get_minio_client()
    return client.presigned_get_object(
        bucket_name=settings.minio_bucket,
        object_name=storage_key,
        expires=timedelta(seconds=expires_in),
    )
