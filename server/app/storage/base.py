"""Storage backend interface."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol


@dataclass
class StoredFile:
    stored_path: str  # FS: relative path / S3: object key
    size_bytes: int
    sha256: str


class StorageBackend(Protocol):
    def save_document_file(
        self,
        *,
        document_id: int,
        original_filename: str,
        source: BinaryIO,
    ) -> StoredFile: ...

    def as_local_path(self, stored_path: str) -> AbstractContextManager[Path]:
        """Provide a local Path to the file. S3 implementations download to a temp file."""
        ...

    def delete_document_dir(self, document_id: int) -> None: ...

    def absolute(self, stored_path: str) -> Path:
        """Return an absolute local Path for direct file serving (e.g. FileResponse).

        Raise NotImplementedError for backends that do not support direct path access
        (e.g. S3). Callers should fall back to presigned_url().
        """
        ...

    def presigned_url(self, stored_path: str, expires_in: int = 3600) -> str | None:
        """Return a time-limited download URL, or None if not supported by this backend."""
        ...
