"""Format retrieved hits as numbered context for LLM prompts."""

from __future__ import annotations

from app.rag.enrich import EnrichedHit
from app.schemas.chat import SourceItem

_SNIPPET_LEN = 400


class CitationNumbering:
    """Hands out [N] numbers across every search of one turn.

    An agent searches more than once per answer (the seeded search, then its own
    follow-ups; comparison runs several in parallel). Numbering each search from
    1 gave one answer several different [1]s, and the UI could only link one of
    them. Here numbers keep counting up across searches, and a passage found
    again keeps the number it was first given, so every [N] names one passage.

    A delegate agent's sources are renumbered through the same instance, so
    what it found joins the caller's sequence instead of starting its own.
    """

    def __init__(self) -> None:
        self._numbers: dict[tuple[int, str], int] = {}

    def number(self, document_id: int, snippet: str) -> int:
        # Keyed by content, not ordinal: pipeline hits may not carry one. The
        # snippet, not the full text, since a delegate's sources carry only that.
        key = (document_id, snippet)
        if key not in self._numbers:
            self._numbers[key] = len(self._numbers) + 1
        return self._numbers[key]

    def assign(self, hits: list[EnrichedHit]) -> list[int]:
        return [self.number(hit.document_id, _snippet(hit)) for hit in hits]


def _snippet(hit: EnrichedHit) -> str:
    return hit.text[:_SNIPPET_LEN].strip()


def build_context_block(hits: list[EnrichedHit], numbers: list[int]) -> str:
    """Return a numbered context string to inject into the LLM prompt."""
    parts: list[str] = []
    for n, hit in zip(numbers, hits, strict=True):
        title = hit.document_title or "Untitled"
        parts.append(f"[{n}] {title}\n{_snippet(hit)}")
    return "\n\n".join(parts)


def hits_to_sources(hits: list[EnrichedHit], numbers: list[int]) -> list[SourceItem]:
    return [
        SourceItem(
            index=n,
            document_id=hit.document_id,
            title=hit.document_title,
            snippet=_snippet(hit),
            score=round(hit.score, 4),
        )
        for n, hit in zip(numbers, hits, strict=True)
    ]
