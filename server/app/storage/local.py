"""Local filesystem storage backend."""

from __future__ import annotations

import hashlib
import re
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

from app.storage.base import StoredFile

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK = 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name).name or "file"
    cleaned = _UNSAFE.sub("_", base).strip("._") or "file"
    return cleaned[:200]


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, stored_path: str) -> Path:
        candidate = (self.root / stored_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as e:
            raise ValueError(f"path escapes storage root: {stored_path}") from e
        return candidate

    def save_document_file(
        self,
        *,
        document_id: int,
        original_filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        safe = _safe_filename(original_filename)
        stored_path = f"documents/{document_id}/{safe}"
        target = self._abs(stored_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total = 0
        with target.open("wb") as out:
            while True:
                buf = source.read(_CHUNK)
                if not buf:
                    break
                hasher.update(buf)
                total += len(buf)
                out.write(buf)

        return StoredFile(stored_path=stored_path, size_bytes=total, sha256=hasher.hexdigest())

    @contextmanager
    def as_local_path(self, stored_path: str) -> Iterator[Path]:
        yield self._abs(stored_path)

    def delete_document_dir(self, document_id: int) -> None:
        target = self._abs(f"documents/{document_id}")
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    def absolute(self, stored_path: str) -> Path:
        """Direct path access — only for endpoints that serve files (e.g. FileResponse)."""
        return self._abs(stored_path)
