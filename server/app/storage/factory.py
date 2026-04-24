"""Storage backend factory."""

from __future__ import annotations

from app.storage.base import StorageBackend

_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is not None:
        return _storage

    from app.core.config import get_settings
    from app.core.paths import resolve_relative
    from app.storage.local import LocalStorage

    settings = get_settings()
    kind = settings.storage.kind

    if kind == "local":
        root = resolve_relative(settings.storage.upload_dir)
        _storage = LocalStorage(root)
    elif kind == "s3":
        from app.storage.s3 import S3Storage

        s3cfg = settings.storage.s3
        if not s3cfg.bucket:
            raise ValueError("storage.s3.bucket is required when storage.kind = 's3'")
        _storage = S3Storage(
            bucket=s3cfg.bucket,
            prefix=s3cfg.prefix,
            region=s3cfg.region,
            endpoint_url=s3cfg.endpoint_url,
            access_key_id=s3cfg.access_key_id,
            secret_access_key=s3cfg.secret_access_key,
        )
    else:
        raise ValueError(f"unsupported storage backend: {kind!r}")

    return _storage
