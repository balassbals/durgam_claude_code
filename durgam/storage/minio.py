"""MinIO object-storage backend implementing StorageBackend."""

from __future__ import annotations

import io
from datetime import timedelta

import structlog
from minio import Minio

from durgam.config import settings

from .backend import StorageBackend

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


class MinioStorageBackend(StorageBackend):
    def __init__(self, client: Minio | None = None, bucket: str | None = None) -> None:
        self._client = client or get_minio_client()
        self._bucket = bucket or settings.minio_bucket

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        log.info("minio_file_stored", key=key, size=len(data))

    def get(self, key: str) -> bytes:
        response = self._client.get_object(
            bucket_name=self._bucket,
            object_name=key,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        self._client.remove_object(
            bucket_name=self._bucket,
            object_name=key,
        )
        log.info("minio_file_deleted", key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(bucket_name=self._bucket, object_name=key)
            return True
        except Exception:
            return False

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.presigned_get_object(
            bucket_name=self._bucket,
            object_name=key,
            expires=timedelta(seconds=expires_in),
        )
