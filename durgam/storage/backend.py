"""StorageBackend ABC — uniform blob-storage interface for local-fs and MinIO."""

from __future__ import annotations

import abc


class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abc.abstractmethod
    def get(self, key: str) -> bytes: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool: ...
