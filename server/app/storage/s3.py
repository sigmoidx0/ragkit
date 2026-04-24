"""Amazon S3 (and S3-compatible) storage backend."""

from __future__ import annotations

import hashlib
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Iterator

from app.storage.base import StoredFile

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK = 1024 * 1024  # 1 MB read buffer


def _safe_filename(name: str) -> str:
    base = Path(name).name or "file"
    cleaned = _UNSAFE.sub("_", base).strip("._") or "file"
    return cleaned[:200]


class S3Storage:
    """StorageBackend implementation for S3 and S3-compatible stores (e.g. MinIO)."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        import boto3

        session = boto3.Session(
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            region_name=region or None,
        )
        self._s3: S3Client = session.client(  # type: ignore[assignment]
            "s3",
            endpoint_url=endpoint_url or None,
        )
        self.bucket = bucket
        self._prefix = prefix.strip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, stored_path: str) -> str:
        """Map stored_path (relative) → S3 object key (with optional prefix)."""
        if self._prefix:
            return f"{self._prefix}/{stored_path}"
        return stored_path

    # ------------------------------------------------------------------
    # StorageBackend protocol
    # ------------------------------------------------------------------

    def save_document_file(
        self,
        *,
        document_id: int,
        original_filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        safe = _safe_filename(original_filename)
        stored_path = f"documents/{document_id}/{safe}"
        key = self._key(stored_path)

        # Buffer to a tempfile so we can compute SHA-256 and then stream to S3.
        hasher = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            while chunk := source.read(_CHUNK):
                hasher.update(chunk)
                total += len(chunk)
                tmp.write(chunk)

        try:
            with tmp_path.open("rb") as f:
                self._s3.upload_fileobj(f, self.bucket, key)
        finally:
            tmp_path.unlink(missing_ok=True)

        return StoredFile(stored_path=stored_path, size_bytes=total, sha256=hasher.hexdigest())

    @contextmanager
    def as_local_path(self, stored_path: str) -> Iterator[Path]:
        """Download the object to a temp file, yield the path, then delete."""
        key = self._key(stored_path)
        suffix = Path(stored_path).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            self._s3.download_file(self.bucket, key, str(tmp_path))
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)

    def delete_document_dir(self, document_id: int) -> None:
        """Delete all objects whose key starts with documents/{document_id}/."""
        prefix = self._key(f"documents/{document_id}/")
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            self._s3.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )

    def absolute(self, stored_path: str) -> Path:
        raise NotImplementedError("S3 storage does not support absolute local paths; use presigned_url()")

    def presigned_url(self, stored_path: str, expires_in: int = 3600) -> str | None:
        key = self._key(stored_path)
        return self._s3.generate_presigned_url(  # type: ignore[return-value]
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
