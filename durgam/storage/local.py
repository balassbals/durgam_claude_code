"""LocalFilesystemBackend — flat UUID-key storage for development."""

from __future__ import annotations

import os
from pathlib import Path

import structlog

from .backend import StorageBackend

log = structlog.get_logger(__name__)


class LocalFilesystemBackend(StorageBackend):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)

    def _key_path(self, key: str) -> Path:
        return self._base / key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        os.makedirs(self._base, exist_ok=True)
        self._key_path(key).write_bytes(data)
        log.info("local_file_stored", key=key, size=len(data))

    def get(self, key: str) -> bytes:
        path = self._key_path(key)
        if not path.is_file():
            raise FileNotFoundError(f"No file at key {key!r}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._key_path(key)
        if path.is_file():
            path.unlink()
            log.info("local_file_deleted", key=key)

    def exists(self, key: str) -> bool:
        return self._key_path(key).is_file()
