from app.storage.base import StorageBackend, StoredFile
from app.storage.local import LocalStorage

__all__ = ["StorageBackend", "StoredFile", "LocalStorage", "get_storage"]

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is not None:
        return _storage

    from app.core.config import get_settings
    from app.core.paths import resolve_relative

    settings = get_settings()
    kind = settings.storage.kind

    if kind == "local":
        root = resolve_relative(settings.storage.upload_dir)
        _storage = LocalStorage(root)
    else:
        raise ValueError(f"unsupported storage backend: {kind!r}")

    return _storage
