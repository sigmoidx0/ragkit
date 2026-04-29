"""add embedding_model to documents

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_embedding_model_name() -> str:
    from app.core.config import get_settings
    cfg = get_settings().embeddings
    if cfg.provider == "ollama":
        return f"ollama/{cfg.ollama.model}"
    if cfg.provider == "tei":
        return "tei"
    if cfg.provider == "vllm":
        return f"vllm/{cfg.vllm.model}"
    if cfg.provider == "azure_openai":
        return f"azure_openai/{cfg.azure_openai.deployment}"
    return cfg.provider


def upgrade() -> None:
    op.add_column("documents", sa.Column("embedding_model", sa.String(255), nullable=True))
    model_name = _current_embedding_model_name()
    op.get_bind().execute(
        sa.text("UPDATE documents SET embedding_model = :m WHERE embedding_model IS NULL"),
        {"m": model_name},
    )


def downgrade() -> None:
    op.drop_column("documents", "embedding_model")
