"""Config loader: merges config.yaml with environment variables.

Non-secret values live in `config.yaml`. Secrets and deployment overrides come
from environment variables (see `.env.example`).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, Field


class ServerSection(BaseModel):
    upload_dir: str = "./data/uploads"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


class DbSection(BaseModel):
    url: str = "sqlite:///./data/ragkit.db"


class VectorstoreSection(BaseModel):
    kind: Literal["qdrant"] = "qdrant"
    url: str = "http://localhost:6333"
    api_key: str | None = None
    collection: str = "documents"
    vector_size: int = 768
    distance: Literal["Cosine", "Dot", "Euclid"] = "Cosine"


class OllamaCfg(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "nomic-embed-text"


class TeiCfg(BaseModel):
    base_url: str = ""


class VllmCfg(BaseModel):
    base_url: str = ""
    model: str = ""


class AzureOpenAICfg(BaseModel):
    endpoint: str = ""
    deployment: str = ""
    api_version: str = "2024-02-01"


class EmbeddingsSection(BaseModel):
    provider: Literal["ollama", "tei", "vllm", "azure_openai"] = "ollama"
    api_key: str | None = None
    ollama: OllamaCfg = Field(default_factory=OllamaCfg)
    tei: TeiCfg = Field(default_factory=TeiCfg)
    vllm: VllmCfg = Field(default_factory=VllmCfg)
    azure_openai: AzureOpenAICfg = Field(default_factory=AzureOpenAICfg)


class JwtSection(BaseModel):
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_ttl_minutes: int = 60
    secret_key: str = "dev-secret-do-not-use-in-production"


class IngestSection(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 150


class SearchSection(BaseModel):
    default_top_k: int = 5
    max_top_k: int = 50


class AdminBootstrapSection(BaseModel):
    email: str = "admin@example.com"
    password_env: str = "INITIAL_ADMIN_PASSWORD"


class Settings(BaseModel):
    server: ServerSection = Field(default_factory=ServerSection)
    db: DbSection = Field(default_factory=DbSection)
    vectorstore: VectorstoreSection = Field(default_factory=VectorstoreSection)
    embeddings: EmbeddingsSection = Field(default_factory=EmbeddingsSection)
    jwt: JwtSection = Field(default_factory=JwtSection)
    ingest: IngestSection = Field(default_factory=IngestSection)
    search: SearchSection = Field(default_factory=SearchSection)
    admin_bootstrap: AdminBootstrapSection = Field(default_factory=AdminBootstrapSection)


def _find_dotenv_paths() -> list[Path]:
    # server/app/core/config.py -> server/
    server_dir = Path(__file__).resolve().parent.parent.parent
    project_root = server_dir.parent
    # Priority: explicit shell env > server/.env > project-root/.env
    return [server_dir / ".env", project_root / ".env"]


def _load_dotenv_into_environment() -> None:
    for dotenv_path in _find_dotenv_paths():
        if not dotenv_path.exists():
            continue
        for key, value in dotenv_values(dotenv_path).items():
            if value is not None:
                os.environ.setdefault(key, value)


def _find_config_path() -> Path:
    explicit = os.getenv("RAGKIT_CONFIG")
    if explicit:
        return Path(explicit).resolve()
    # server/app/core/config.py -> server/config.yaml
    return (Path(__file__).resolve().parent.parent.parent / "config.yaml").resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top level of {path}, got {type(data).__name__}")
    return data


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if jwt_secret:
        raw.setdefault("jwt", {})["secret_key"] = jwt_secret

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        raw.setdefault("db", {})["url"] = db_url

    vs_key = os.getenv("VECTORSTORE_API_KEY")
    if vs_key:
        raw.setdefault("vectorstore", {})["api_key"] = vs_key

    emb_key = os.getenv("EMBEDDING_API_KEY")
    if emb_key:
        raw.setdefault("embeddings", {})["api_key"] = emb_key

    return raw


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv_into_environment()
    path = _find_config_path()
    raw = _load_yaml(path)
    raw = _apply_env_overrides(raw)
    return Settings(**raw)


def reset_settings_cache() -> None:
    get_settings.cache_clear()
