"""Debug-image blob store backed by MinIO (S3-compatible).

The rest of the service depends on the ``DebugImageStore`` protocol; a
concrete ``MinIOStore`` is provided for production, and tests use an
in-memory fake.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class DebugImageStore(Protocol):
    async def put(self, key: str, jpeg: bytes) -> str: ...
    async def stream(self, key: str) -> AsyncIterator[bytes]: ...
    async def exists(self, key: str) -> bool: ...


class MinIOStore:
    """Minimal MinIO-backed store.

    The underlying ``minio`` client is synchronous; we wrap its calls
    in ``asyncio.to_thread`` so the event loop is never blocked.
    """

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        import asyncio

        from minio import Minio

        self._asyncio = asyncio
        self._bucket = bucket
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    async def put(self, key: str, jpeg: bytes) -> str:
        def _put() -> None:
            self._client.put_object(
                self._bucket,
                key,
                io.BytesIO(jpeg),
                length=len(jpeg),
                content_type="image/jpeg",
            )

        await self._asyncio.to_thread(_put)
        return key

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        def _get() -> bytes:
            resp = self._client.get_object(self._bucket, key)
            try:
                data: bytes = resp.read()
                return data
            finally:
                resp.close()
                resp.release_conn()

        data: bytes = await self._asyncio.to_thread(_get)

        async def _iter() -> AsyncIterator[bytes]:
            chunk = 64 * 1024
            for i in range(0, len(data), chunk):
                yield data[i : i + chunk]

        return _iter()

    async def exists(self, key: str) -> bool:
        def _stat() -> bool:
            try:
                self._client.stat_object(self._bucket, key)
                return True
            except Exception:
                return False

        return await self._asyncio.to_thread(_stat)


class InMemoryBlobStore:
    """In-memory fake used by tests and when MinIO is unavailable."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def put(self, key: str, jpeg: bytes) -> str:
        self._blobs[key] = jpeg
        return key

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        data = self._blobs.get(key, b"")

        async def _iter() -> AsyncIterator[bytes]:
            yield data

        return _iter()

    async def exists(self, key: str) -> bool:
        return key in self._blobs
