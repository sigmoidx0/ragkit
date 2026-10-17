"""Reading a chat session's history back out of the LangGraph checkpoint.

Several features address "the Nth answer in a session" — stored citations,
feedback, the message list — and they must all count the same way. An
assistant turn is an AIMessage with content; empty AIMessages (a bare tool
call) are not answers the user saw.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


@dataclass(frozen=True)
class Turn:
    role: str  # "user" | "assistant"
    content: str
    # Assistant turns only: 0-based position among the session's answers.
    turn_index: int | None = None


def session_turns(messages: Sequence[BaseMessage]) -> list[Turn]:
    turns: list[Turn] = []
    answers = 0
    for msg in messages:
        if isinstance(msg, HumanMessage):
            turns.append(Turn("user", str(msg.content)))
        elif isinstance(msg, AIMessage) and msg.content:
            turns.append(Turn("assistant", str(msg.content), answers))
            answers += 1
    return turns


SESSION_TITLE_MAX = 40


def title_from_message(message: str) -> str:
    """A session's title: its first question, on one line, cut to a readable length."""
    text = " ".join(message.split())
    return text if len(text) <= SESSION_TITLE_MAX else text[: SESSION_TITLE_MAX - 1].rstrip() + "…"


def count_answers(messages: Sequence[BaseMessage]) -> int:
    """How many answers the session already has — the index the next one gets."""
    return sum(1 for t in session_turns(messages) if t.role == "assistant")


def question_and_answer(messages: Sequence[BaseMessage], turn_index: int) -> tuple[str, str] | None:
    """The answer at `turn_index` and the user message it replied to."""
    turns = session_turns(messages)
    for i, turn in enumerate(turns):
        if turn.turn_index == turn_index:
            question = next((t.content for t in reversed(turns[:i]) if t.role == "user"), "")
            return question, turn.content
    return None
