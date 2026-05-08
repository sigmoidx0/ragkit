"""Conversation persistence interface.

Phase 1: stub only — /chat is stateless (client sends full messages[] each request).
Phase 2: replace StubConversationStore with a DB-backed implementation when
multi-turn agent state needs to be persisted across sessions.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.chat import ChatMessage


class ConversationStore(Protocol):
    def create(self, user_id: int) -> str: ...
    def append(self, conversation_id: str, message: ChatMessage) -> None: ...
    def fetch(self, conversation_id: str) -> list[ChatMessage]: ...


class StubConversationStore:
    def create(self, user_id: int) -> str:
        raise NotImplementedError

    def append(self, conversation_id: str, message: ChatMessage) -> None:
        raise NotImplementedError

    def fetch(self, conversation_id: str) -> list[ChatMessage]:
        raise NotImplementedError
