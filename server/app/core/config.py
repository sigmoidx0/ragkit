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


class S3Section(BaseModel):
    bucket: str = ""
    prefix: str = ""
    region: str | None = None
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None


class StorageSection(BaseModel):
    kind: Literal["local", "s3"] = "local"
    upload_dir: str = "./data/uploads"
    s3: S3Section = Field(default_factory=S3Section)


class ServerSection(BaseModel):
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


class RerankerSection(BaseModel):
    provider: Literal["cohere", "cross_encoder"]
    model: str
    api_key: str | None = None
    fetch_k_multiplier: int = 4


class SearchSection(BaseModel):
    default_top_k: int = 5
    max_top_k: int = 50
    hybrid: bool = False
    reranker: RerankerSection | None = None


class AdminBootstrapSection(BaseModel):
    email: str = "platform.admin@ragkit.io"
    password_env: str = "INITIAL_ADMIN_PASSWORD"


class LlmOllamaCfg(BaseModel):
    base_url: str = "http://localhost:11434"


class LlmVllmCfg(BaseModel):
    base_url: str = ""


class LlmSection(BaseModel):
    provider: Literal["openai", "anthropic", "ollama", "vllm"] = "ollama"
    model: str = "qwen2.5:1.5b"
    api_key: str | None = None
    temperature: float = 0.0
    max_tokens: int = 2048
    ollama: LlmOllamaCfg = Field(default_factory=LlmOllamaCfg)
    vllm: LlmVllmCfg = Field(default_factory=LlmVllmCfg)


class ChatSection(BaseModel):
    enabled: bool = True
    default_top_k: int = 5
    fallback_system_prompt: str = (
        "You are a helpful assistant. Answer questions based on the provided context. "
        "Cite sources inline using [N] notation (e.g. \"According to the policy [1], ...\"). "
        "If the context does not contain enough information, say so clearly."
    )


class Settings(BaseModel):
    server: ServerSection = Field(default_factory=ServerSection)
    storage: StorageSection = Field(default_factory=StorageSection)
    db: DbSection = Field(default_factory=DbSection)
    vectorstore: VectorstoreSection = Field(default_factory=VectorstoreSection)
    embeddings: EmbeddingsSection = Field(default_factory=EmbeddingsSection)
    jwt: JwtSection = Field(default_factory=JwtSection)
    ingest: IngestSection = Field(default_factory=IngestSection)
    search: SearchSection = Field(default_factory=SearchSection)
    admin_bootstrap: AdminBootstrapSection = Field(default_factory=AdminBootstrapSection)
    llm: LlmSection = Field(default_factory=LlmSection)
    chat: ChatSection = Field(default_factory=ChatSection)


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

    reranker_key = os.getenv("RERANKER_API_KEY")
    if reranker_key:
        raw.setdefault("search", {}).setdefault("reranker", {})["api_key"] = reranker_key

    s3_bucket = os.getenv("S3_BUCKET")
    if s3_bucket:
        raw.setdefault("storage", {}).setdefault("s3", {})["bucket"] = s3_bucket
    s3_endpoint = os.getenv("S3_ENDPOINT_URL")
    if s3_endpoint:
        raw.setdefault("storage", {}).setdefault("s3", {})["endpoint_url"] = s3_endpoint
    s3_key = os.getenv("AWS_ACCESS_KEY_ID")
    if s3_key:
        raw.setdefault("storage", {}).setdefault("s3", {})["access_key_id"] = s3_key
    s3_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    if s3_secret:
        raw.setdefault("storage", {}).setdefault("s3", {})["secret_access_key"] = s3_secret
    s3_region = os.getenv("AWS_DEFAULT_REGION")
    if s3_region:
        raw.setdefault("storage", {}).setdefault("s3", {})["region"] = s3_region

    llm_key = os.getenv("LLM_API_KEY")
    if llm_key:
        raw.setdefault("llm", {})["api_key"] = llm_key

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
