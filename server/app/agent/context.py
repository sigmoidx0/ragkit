"""Per-turn conversation context: a standalone query and a bounded history.

The graph's first node handles two problems of multi-turn chat, once per turn:

- Follow-ups. "그럼 마감은 언제야?" means nothing on its own, yet the supervisor,
  the seeded search and the comparison planner all act on the latest question.
  It is rewritten into a standalone `query` using the conversation so far.
- Length. Every message stays in the checkpoint — the session view and the
  turn numbering of citations and feedback read it — so nothing is deleted.
  Instead, once the unsummarized part grows past a token budget, its older
  messages are folded into a running `summary`, and agents see the summary plus
  the recent messages (`conversation_window`).

Both calls are skipped when there is nothing to do, so a first question costs
no extra model call.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately

from app.agent.agents import INTERNAL_LLM_TAG
from app.agent.state import MultiAgentState

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\s?\[\d+\]")
# Old answers are long; the rewrite needs their gist, not every word.
_TRANSCRIPT_ANSWER_CHARS = 600

_SUMMARY_PROMPT = """\
You maintain a running summary of a conversation between a user and a document assistant.
Merge the new messages into the existing summary. Keep what the user may refer back to:
the topics asked about, facts and numbers given in answers, names, decisions, open questions.
Drop pleasantries and citation markers like [1]. Write in the conversation's language,
at most about 250 words. Reply with the summary only."""

_REWRITE_PROMPT = """\
Rewrite the user's latest message as a standalone search query that is fully understandable
without the conversation: resolve pronouns and references ("그거", "the second one", "그럼 마감은?")
from the conversation. Keep the user's language. If the message already stands alone, return it
unchanged. Reply with the query only."""


def _last_human_index(messages: Sequence[BaseMessage]) -> int | None:
    return next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)), None)


def _transcript(summary: str, messages: Sequence[BaseMessage]) -> str:
    lines = [f"(Summary of earlier conversation) {summary}"] if summary else []
    for m in messages:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        elif m.content:
            answer = _CITATION.sub("", str(m.content))
            lines.append(f"Assistant: {answer[:_TRANSCRIPT_ANSWER_CHARS]}")
    return "\n".join(lines)


def fold_point(messages: Sequence[BaseMessage], covered: int, max_tokens: int, keep: int) -> int:
    """Index up to which messages should be summarized; `covered` means none.

    The kept tail always starts at a user message, so the model never sees an
    answer whose question was folded away, and the current question (the last
    message) is never folded.
    """
    if count_tokens_approximately(list(messages[covered:])) <= max_tokens:
        return covered
    end = len(messages) - keep
    while end > covered and not isinstance(messages[end], HumanMessage):
        end -= 1
    return max(end, covered)


def conversation_window(state: MultiAgentState) -> list[BaseMessage]:
    """What an agent sees of the conversation: the summary, then the recent messages."""
    covered = state.get("summarized") or 0
    recent = list(state["messages"][covered:])
    summary = state.get("summary") or ""
    if not summary:
        return recent
    # A user message rather than a system one: some providers reject a system
    # message anywhere but first, and the agent's own prompt already is first.
    note = HumanMessage(content=f"<conversation_summary>\n{summary}\n</conversation_summary>")
    return [note, *recent]


def make_prepare_node(llm: BaseChatModel, max_tokens: int, keep_messages: int):
    internal = llm.with_config(tags=[INTERNAL_LLM_TAG])

    async def summarize(summary: str, messages: Sequence[BaseMessage]) -> str | None:
        existing = summary or "(none yet)"
        try:
            result = await internal.ainvoke([
                SystemMessage(content=_SUMMARY_PROMPT),
                HumanMessage(content=f"Existing summary:\n{existing}\n\nNew messages:\n{_transcript('', messages)}"),
            ])
        except Exception as exc:  # an unsummarized turn is still answerable
            logger.warning("[prepare] summarizing history failed: %s", exc)
            return None
        return str(result.content).strip() or None

    async def standalone_query(summary: str, earlier: Sequence[BaseMessage], question: str) -> str:
        try:
            result = await internal.ainvoke([
                SystemMessage(content=_REWRITE_PROMPT),
                HumanMessage(
                    content=f"<conversation>\n{_transcript(summary, earlier)}\n</conversation>\n\n"
                    f"Latest message: {question}"
                ),
            ])
        except Exception as exc:  # the original words still search reasonably
            logger.warning("[prepare] rewriting the question failed: %s", exc)
            return question
        query = str(result.content).strip().strip('"').strip()
        # A rewrite that rambles has stopped being a query.
        return query if query and len(query) <= 4 * len(question) + 200 else question

    async def prepare(state: MultiAgentState) -> dict:
        messages = state["messages"]
        summary = state.get("summary") or ""
        covered = state.get("summarized") or 0
        update: dict = {}

        end = fold_point(messages, covered, max_tokens, keep_messages)
        if end > covered and (folded := await summarize(summary, messages[covered:end])) is not None:
            logger.debug("[prepare] folded messages %d..%d into the summary", covered, end)
            summary, covered = folded, end
            update.update(summary=summary, summarized=covered)

        last = _last_human_index(messages)
        question = str(messages[last].content) if last is not None else ""
        earlier = messages[covered:last] if last is not None else []
        update["query"] = await standalone_query(summary, earlier, question) if (summary or earlier) else question
        logger.debug("[prepare] query=%r", update["query"][:120])
        return update

    return prepare
