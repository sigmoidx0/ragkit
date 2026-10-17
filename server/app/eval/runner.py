"""Run an evaluation: every case through the agent's real graph, then score it.

Cases go through exactly the code path chat uses (build_multi_agent_graph), so a
score reflects what users get. Per case we record the route taken, the sources,
latency, tool calls and tokens; then:

- retrieval hit / rank, when the case names the document a good answer needs;
- groundedness, a 1–5 LLM judgement of whether the answer is supported by the
  passages it retrieved.

The judge is always config.yaml's default model, never the agent's own, so two
runs on different models are graded by the same yardstick.
"""

from __future__ import annotations

import logging
import statistics
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.config import load_system_prompt
from app.agent.delegation import DELEGATE_TOOL_PREFIX
from app.agent.graph import build_multi_agent_graph
from app.core.config import get_settings
from app.db.models import Agent, EvalRun
from app.db.session import SessionLocal
from app.llm import get_chat_model
from app.schemas.agent_config import AgentConfig
from app.schemas.chat import SourceItem
from app.schemas.evals import EvalCase, EvalCaseResult, EvalSummary

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """\
You grade whether an assistant's answer is supported by the retrieved passages it was given.
Score from 1 to 5:
5 — every factual claim is supported by the passages, or the answer correctly says the passages lack the information
4 — supported, with minor unsupported detail
3 — partly supported, or too vague to check
2 — mostly unsupported
1 — contradicts the passages or ignores them
Judge support only, not style or language. Give the score and one short reason."""

_MAX_PASSAGES = 8


class _Judgement(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str


def _judge_model_name() -> str:
    llm = get_settings().llm
    return f"{llm.provider} · {llm.model}"


async def _judge(question: str, answer: str, sources: list[SourceItem]) -> _Judgement | None:
    passages = "\n\n".join(f"[{s.index}] {s.title or ''}\n{s.snippet}" for s in sources[:_MAX_PASSAGES]) or "(none)"
    try:
        return await get_chat_model().with_structured_output(_Judgement).ainvoke([
            SystemMessage(content=_JUDGE_PROMPT),
            HumanMessage(content=f"Question:\n{question}\n\nPassages:\n{passages}\n\nAnswer:\n{answer}"),
        ])
    except Exception as exc:  # a judge failure shouldn't sink the case
        logger.warning("eval judge failed: %s", exc)
        return None


def keyword_recall(answer: str, keywords: list[str]) -> tuple[float, list[str]]:
    """Share of `keywords` present in `answer`, and the ones that aren't.

    Case- and whitespace-insensitive, so "33 Hz" matches "33Hz" — Korean
    spacing in particular varies between the document and the answer.
    """
    squashed = "".join(answer.lower().split())
    missing = [k for k in keywords if "".join(k.lower().split()) not in squashed]
    return round((len(keywords) - len(missing)) / len(keywords), 3), missing


def _ranked_documents(sources: list[SourceItem]) -> list[int]:
    """Distinct document ids in the order retrieval surfaced them."""
    seen: list[int] = []
    for s in sources:
        if s.document_id not in seen:
            seen.append(s.document_id)
    return seen


async def run_case(
    db: Session, agent: Agent, agent_cfg: AgentConfig, system_prompt: str, case: EvalCase, user_id: int | None
) -> EvalCaseResult:
    result = EvalCaseResult(question=case.question, expected_document_id=case.expected_document_id)
    t0 = time.perf_counter()
    try:
        built = build_multi_agent_graph(
            db, agent, agent_cfg, system_prompt, agent_cfg.default_retrieval_mode, user_id=user_id
        )
        async for ev in built.graph.astream_events(
            {"messages": [HumanMessage(content=case.question)], "agent_type": ""}, version="v2"
        ):
            kind, name = ev["event"], ev.get("name", "")
            if kind == "on_chain_end" and name == "supervisor":
                result.route = (ev["data"].get("output") or {}).get("agent_type")
            elif kind == "on_tool_start" and (name == "retrieval" or name.startswith(DELEGATE_TOOL_PREFIX)):
                result.tool_calls += 1
            elif kind == "on_chat_model_end":
                usage = getattr(ev["data"].get("output"), "usage_metadata", None) or {}
                result.input_tokens += usage.get("input_tokens") or 0
                result.output_tokens += usage.get("output_tokens") or 0
            elif kind == "on_chain_end" and not ev.get("parent_ids"):
                messages = (ev["data"].get("output") or {}).get("messages") or []
                ai = [m for m in messages if isinstance(m, AIMessage)]
                result.answer = str(ai[-1].content) if ai else ""
        if result.route is None:
            # No supervisor ran — a single-route agent goes straight to it.
            result.route = next(iter(agent_cfg.active_routes(agent_cfg.default_retrieval_mode)), None)
        result.sources = [s for found in built.sources_store.values() for s in found]
    except Exception as exc:
        logger.warning("eval case failed: %s", exc)
        result.error = str(exc)[:500]
        result.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return result
    result.latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    if case.expected_keywords:
        result.keyword_recall, result.missing_keywords = keyword_recall(result.answer, case.expected_keywords)

    if case.expected_document_id is not None:
        ranked = _ranked_documents(result.sources)
        result.hit = case.expected_document_id in ranked
        result.rank = ranked.index(case.expected_document_id) + 1 if result.hit else None

    judgement = await _judge(case.question, result.answer, result.sources)
    if judgement is not None:
        result.groundedness, result.judge_reason = judgement.score, judgement.reason
    return result


def summarize(cases: list[EvalCase], results: list[EvalCaseResult]) -> EvalSummary:
    ok = [r for r in results if r.error is None]
    expected = [r for r in ok if r.expected_document_id is not None]
    graded = [r.groundedness for r in ok if r.groundedness is not None]
    latencies = sorted(r.latency_ms for r in ok)

    def mean(values: list[float]) -> float | None:
        return round(statistics.fmean(values), 3) if values else None

    return EvalSummary(
        cases=len(cases),
        completed=len(results),
        errors=len(results) - len(ok),
        hit_rate=mean([1.0 if r.hit else 0.0 for r in expected]),
        mrr=mean([1.0 / r.rank if r.rank else 0.0 for r in expected]),
        keyword_recall=mean([r.keyword_recall for r in ok if r.keyword_recall is not None]),
        avg_groundedness=mean(graded),
        avg_latency_ms=mean(latencies),
        p95_latency_ms=latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))] if latencies else None,
        avg_tool_calls=mean([r.tool_calls for r in ok]),
        total_tokens=sum(r.input_tokens + r.output_tokens for r in ok),
        judge_model=_judge_model_name(),
    )


async def execute_eval_run(run_id: int, user_id: int | None) -> None:
    """Background task: run every case, saving after each so the UI sees progress."""
    db = SessionLocal()
    try:
        run = db.get(EvalRun, run_id)
        if run is None:
            return
        run.status = "running"
        db.commit()

        agent_cfg = AgentConfig.model_validate(run.config_snapshot)
        # Runs created before prompts were snapshotted fall back to the active one.
        agent = db.get(Agent, run.agent_id)
        if agent is None:
            raise RuntimeError(f"agent {run.agent_id} no longer exists")
        system_prompt = run.system_prompt or load_system_prompt(db, agent.id)
        cases = [EvalCase.model_validate(c) for c in run.cases]
        results: list[EvalCaseResult] = []
        for case in cases:
            results.append(await run_case(db, agent, agent_cfg, system_prompt, case, user_id))
            # Reassign (not append) so SQLAlchemy sees the JSON column change.
            run.results = [r.model_dump(mode="json") for r in results]
            run.summary = summarize(cases, results).model_dump(mode="json")
            db.commit()

        run.status = "done"
        db.commit()
    except Exception as exc:
        logger.exception("eval run %d failed", run_id)
        db.rollback()
        run = db.get(EvalRun, run_id)
        if run is not None:
            run.status, run.error = "failed", str(exc)[:1000]
            db.commit()
    finally:
        db.close()


def fail_interrupted_runs() -> None:
    """Runs left pending/running by a restart will never finish — say so."""
    db = SessionLocal()
    try:
        for run in db.query(EvalRun).filter(EvalRun.status.in_(("pending", "running"))):
            run.status, run.error = "failed", "interrupted by a server restart"
        db.commit()
    finally:
        db.close()
