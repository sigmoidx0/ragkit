"""Local filesystem storage: one folder per document, SHA-256 checksum."""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.core.paths import resolve_relative

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_CHUNK = 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name).name or "file"
    cleaned = _UNSAFE.sub("_", base).strip("._") or "file"
    return cleaned[:200]


@dataclass
class StoredFile:
    relative_path: str
    absolute_path: Path
    size_bytes: int
    sha256: str


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _abs(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as e:
            raise ValueError(f"path escapes storage root: {relative}") from e
        return candidate

    def save_document_file(
        self,
        *,
        document_id: int,
        original_filename: str,
        source: BinaryIO,
    ) -> StoredFile:
        safe = _safe_filename(original_filename)
        relative = f"documents/{document_id}/{safe}"
        target = self._abs(relative)
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

        return StoredFile(
            relative_path=relative,
            absolute_path=target,
            size_bytes=total,
            sha256=hasher.hexdigest(),
        )

    def absolute(self, relative_path: str) -> Path:
        return self._abs(relative_path)

    def delete_document_dir(self, document_id: int) -> None:
        target = self._abs(f"documents/{document_id}")
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


_storage: FileStorage | None = None


def get_storage() -> FileStorage:
    global _storage
    if _storage is None:
        settings = get_settings()
        root = resolve_relative(settings.server.upload_dir)
        _storage = FileStorage(root)
    return _storage
