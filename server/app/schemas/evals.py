from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_config import AgentConfig
from app.schemas.chat import SourceItem


class EvalCase(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # The document a good answer should come from. Optional: without it the
    # case still measures groundedness, latency and cost, just not retrieval hit.
    expected_document_id: int | None = None
    # Facts a correct answer must state ("정현파", "33 Hz"). The other metrics
    # can't tell a right answer from a confident "the documents don't cover
    # this": the right document may be hit at the wrong chunk, and the judge
    # only checks the answer against what was retrieved. This checks the answer.
    expected_keywords: list[str] = Field(default_factory=list, max_length=10)


class EvalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cases: list[EvalCase] = Field(min_length=1, max_length=30)
    # None runs the agent's saved config; a config here evaluates a variant
    # without saving it — how A/B comparisons are made.
    config: AgentConfig | None = None
    # One of the agent's saved system prompts to run with; None uses the
    # active one. Either way its text is snapshotted onto the run.
    system_prompt_id: int | None = None


class EvalCaseResult(BaseModel):
    question: str
    expected_document_id: int | None = None
    answer: str = ""
    route: str | None = None
    sources: list[SourceItem] = Field(default_factory=list)
    latency_ms: float = 0.0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    # Retrieval: was the expected document among the sources, and at what rank.
    hit: bool | None = None
    rank: int | None = None
    # Share of expected_keywords the answer contains; None when none were given.
    keyword_recall: float | None = None
    missing_keywords: list[str] = Field(default_factory=list)
    # LLM-judged: is the answer supported by the retrieved passages (1–5).
    groundedness: int | None = None
    judge_reason: str | None = None
    error: str | None = None


class EvalSummary(BaseModel):
    cases: int
    completed: int
    errors: int
    hit_rate: float | None  # None when no case names an expected document
    mrr: float | None
    # None when no case lists expected keywords — and on runs saved before this
    # metric existed, so their stored summaries still load.
    keyword_recall: float | None = None
    avg_groundedness: float | None
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    avg_tool_calls: float | None
    total_tokens: int
    judge_model: str


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    name: str
    status: str
    config_snapshot: AgentConfig
    prompt_name: str | None
    cases: list[EvalCase]
    results: list[EvalCaseResult]
    summary: EvalSummary | None
    error: str | None
    created_at: datetime
    updated_at: datetime
