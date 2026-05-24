"""Unit tests for StorageBackend implementations."""

from unittest.mock import MagicMock, patch

import pytest

from durgam.storage.backend import StorageBackend
from durgam.storage.local import LocalFilesystemBackend
from durgam.storage.minio import MinioStorageBackend


class TestLocalFilesystemBackend:
    def test_implements_interface(self):
        assert issubclass(LocalFilesystemBackend, StorageBackend)

    def test_put_and_get_round_trip(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        backend.put("abc123", b"hello world", "text/plain")
        assert backend.get("abc123") == b"hello world"

    def test_exists_true_after_put(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        backend.put("key1", b"data", "application/octet-stream")
        assert backend.exists("key1") is True

    def test_exists_false_before_put(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        assert backend.exists("nonexistent") is False

    def test_delete_removes_file(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        backend.put("del_me", b"data", "text/plain")
        assert backend.exists("del_me") is True
        backend.delete("del_me")
        assert backend.exists("del_me") is False

    def test_delete_nonexistent_is_silent(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        backend.delete("no_such_key")

    def test_get_nonexistent_raises(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            backend.get("missing")

    def test_put_creates_base_dir(self, tmp_path):
        deep = tmp_path / "nested" / "dir"
        backend = LocalFilesystemBackend(str(deep))
        backend.put("key", b"x", "text/plain")
        assert backend.get("key") == b"x"

    def test_binary_round_trip(self, tmp_path):
        backend = LocalFilesystemBackend(str(tmp_path))
        data = bytes(range(256))
        backend.put("binary", data, "application/octet-stream")
        assert backend.get("binary") == data


class TestMinioStorageBackend:
    def test_implements_interface(self):
        assert issubclass(MinioStorageBackend, StorageBackend)

    def test_put_delegates_to_client(self):
        client = MagicMock()
        backend = MinioStorageBackend(client=client, bucket="test-bucket")
        backend.put("key1", b"data", "image/png")
        client.put_object.assert_called_once()
        call_kwargs = client.put_object.call_args
        assert call_kwargs.kwargs["bucket_name"] == "test-bucket"
        assert call_kwargs.kwargs["object_name"] == "key1"
        assert call_kwargs.kwargs["content_type"] == "image/png"

    def test_get_delegates_to_client(self):
        client = MagicMock()
        response = MagicMock()
        response.read.return_value = b"file-content"
        client.get_object.return_value = response
        backend = MinioStorageBackend(client=client, bucket="b")
        result = backend.get("k")
        assert result == b"file-content"
        response.close.assert_called_once()
        response.release_conn.assert_called_once()

    def test_delete_delegates_to_client(self):
        client = MagicMock()
        backend = MinioStorageBackend(client=client, bucket="b")
        backend.delete("k")
        client.remove_object.assert_called_once_with(bucket_name="b", object_name="k")

    def test_exists_returns_true_on_stat(self):
        client = MagicMock()
        client.stat_object.return_value = MagicMock()
        backend = MinioStorageBackend(client=client, bucket="b")
        assert backend.exists("k") is True

    def test_exists_returns_false_on_exception(self):
        client = MagicMock()
        client.stat_object.side_effect = Exception("not found")
        backend = MinioStorageBackend(client=client, bucket="b")
        assert backend.exists("k") is False

    @patch("durgam.storage.minio.get_minio_client")
    def test_default_constructor_uses_global_client(self, mock_get):
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        backend = MinioStorageBackend()
        backend.put("k", b"d", "text/plain")
        mock_client.put_object.assert_called_once()
