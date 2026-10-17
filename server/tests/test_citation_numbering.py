"""Citation numbers across the several searches one answer makes."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from app.agent.delegation import renumber_sources
from app.agent.tools import make_retrieval_tool
from app.rag.citation import CitationNumbering
from app.rag.enrich import EnrichedHit
from app.schemas.chat import SourceItem


def _hit(document_id: int, text: str) -> EnrichedHit:
    return EnrichedHit(document_id=document_id, document_title=f"doc {document_id}", ordinal=0, score=0.5, text=text, metadata={})


def test_numbers_continue_across_searches_and_reuse_repeats() -> None:
    numbering = CitationNumbering()
    assert numbering.assign([_hit(1, "a"), _hit(2, "b")]) == [1, 2]
    # A second search: one passage already cited keeps its number, new ones continue.
    assert numbering.assign([_hit(2, "b"), _hit(3, "c")]) == [2, 3]
    # Same document, different chunk → its own number.
    assert numbering.assign([_hit(1, "a2")]) == [4]


def test_retrieval_tool_never_reuses_a_number_for_another_passage() -> None:
    results = {
        "seed question": [_hit(1, "a"), _hit(2, "b")],
        "follow-up": [_hit(3, "c"), _hit(1, "a")],
    }
    with patch("app.agent.tools.run_search", side_effect=lambda _db, q: results[q.query]):
        sources_store: dict = {}
        tool = make_retrieval_tool(
            db=None, workspace_id=1, top_k=2, sources_store=sources_store, numbering=CitationNumbering()
        )
        asyncio.run(tool.ainvoke({"query": "seed question"}))
        context = asyncio.run(tool.ainvoke({"query": "follow-up"}))

    assert context.startswith("[3] doc 3")
    by_index: dict[int, str] = {}
    for sources in sources_store.values():
        for s in sources:
            # Every appearance of an index must be the same passage.
            assert by_index.setdefault(s.index, s.snippet) == s.snippet
    assert sorted(by_index) == [1, 2, 3]


def test_delegate_sources_join_the_callers_sequence() -> None:
    numbering = CitationNumbering()
    numbering.assign([_hit(1, "a"), _hit(2, "b")])  # the caller's own search: [1], [2]
    # The delegate numbered its own sources from 1; one is a passage the caller already has.
    found = [
        SourceItem(index=1, document_id=9, title="other", snippet="x", score=0.9),
        SourceItem(index=2, document_id=2, title="doc 2", snippet="b", score=0.8),
    ]
    sources, answer = renumber_sources(found, "X holds [1], and Y [2][7].", numbering)

    assert [(s.index, s.document_id) for s in sources] == [(3, 9), (2, 2)]
    # [7] named nothing the delegate found, so it's dropped, not left dangling.
    assert answer == "X holds [3], and Y [2]."
