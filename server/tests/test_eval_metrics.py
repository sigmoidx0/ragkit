"""Evaluation scoring that doesn't need a model."""

from __future__ import annotations

from app.eval.runner import keyword_recall, summarize
from app.schemas.evals import EvalCase, EvalCaseResult


def _result(**kw) -> EvalCaseResult:
    return EvalCaseResult(question="q", **kw)


def test_summary_averages_only_cases_that_define_each_metric() -> None:
    cases = [EvalCase(question="q")] * 3
    results = [
        _result(expected_document_id=1, hit=True, rank=1, keyword_recall=1.0, groundedness=5, latency_ms=100),
        _result(expected_document_id=1, hit=False, rank=None, keyword_recall=0.0, groundedness=5, latency_ms=300),
        _result(groundedness=3, latency_ms=200),  # no expectations: excluded from hit / keyword averages
    ]
    s = summarize(cases, results)
    assert (s.hit_rate, s.mrr, s.keyword_recall) == (0.5, 0.5, 0.5)
    assert s.avg_groundedness == 4.333
    assert s.avg_latency_ms == 200


def test_errors_are_counted_but_not_scored() -> None:
    s = summarize([EvalCase(question="q")] * 2, [_result(error="boom"), _result(groundedness=4, latency_ms=50)])
    assert (s.errors, s.completed, s.avg_groundedness, s.keyword_recall) == (1, 2, 4.0, None)


def test_keyword_recall_ignores_case_and_spacing() -> None:
    answer = "진동 파형은 정현파로 하며, 주파수는 33Hz 입니다."
    assert keyword_recall(answer, ["정현파", "33 Hz", "진동시험기"]) == (0.667, ["진동시험기"])


def test_summaries_saved_before_keyword_recall_still_load() -> None:
    from app.schemas.evals import EvalSummary

    old = {"cases": 1, "completed": 1, "errors": 0, "hit_rate": 1.0, "mrr": 1.0, "avg_groundedness": 5.0,
           "avg_latency_ms": 10.0, "p95_latency_ms": 10.0, "avg_tool_calls": 1.0, "total_tokens": 5,
           "judge_model": "ollama · qwen2.5:14b"}
    assert EvalSummary.model_validate(old).keyword_recall is None
