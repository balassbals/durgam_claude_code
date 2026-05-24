"""Storage layer — backend abstraction + factory."""

from __future__ import annotations

from .backend import StorageBackend
from .local import LocalFilesystemBackend
from .minio import MinioStorageBackend, get_minio_client


def get_storage_backend() -> StorageBackend:
    from durgam.config import settings

    if settings.minio_endpoint and settings.environment != "development":
        return MinioStorageBackend()
    return LocalFilesystemBackend(settings.upload_base_path)


__all__ = [
    "StorageBackend",
    "LocalFilesystemBackend",
    "MinioStorageBackend",
    "get_storage_backend",
    "get_minio_client",
]
