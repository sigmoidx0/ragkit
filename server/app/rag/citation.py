"""Format retrieved hits as numbered context for LLM prompts."""

from __future__ import annotations

from app.rag.enrich import EnrichedHit
from app.schemas.chat import SourceItem

_SNIPPET_LEN = 400


def build_context_block(hits: list[EnrichedHit]) -> str:
    """Return a numbered context string to inject into the LLM prompt."""
    parts: list[str] = []
    for i, hit in enumerate(hits, start=1):
        title = hit.document_title or "Untitled"
        snippet = hit.text[:_SNIPPET_LEN].strip()
        parts.append(f"[{i}] {title}\n{snippet}")
    return "\n\n".join(parts)


def hits_to_sources(hits: list[EnrichedHit]) -> list[SourceItem]:
    return [
        SourceItem(
            index=i,
            document_id=hit.document_id,
            title=hit.document_title,
            snippet=hit.text[:_SNIPPET_LEN].strip(),
            score=round(hit.score, 4),
        )
        for i, hit in enumerate(hits, start=1)
    ]
