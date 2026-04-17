"""Filesystem helpers rooted at the server package directory."""

from __future__ import annotations

from pathlib import Path


def server_root() -> Path:
    # server/app/core/paths.py -> server/
    return Path(__file__).resolve().parent.parent.parent


def resolve_relative(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return (server_root() / p).resolve()
