"""Build LangChain messages list for the chat generation chain."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.schemas.chat import ChatMessage

_CONTEXT_INSTRUCTION = (
    "\n\nUse only the information provided in the context below to answer the user's question. "
    "Cite sources inline using [N] notation (e.g. \"According to the policy [1], ...\"). "
    "If the context does not contain enough information, say so clearly. "
    "Always respond in the same language as the user's question. "
    "If the user asks in Korean, respond in Korean.\n\nContext:\n{context}"
)


def build_messages(
    system_prompt: str,
    history: list[ChatMessage],
    context_block: str,
) -> list[SystemMessage | HumanMessage | AIMessage]:
    full_system = system_prompt + _CONTEXT_INSTRUCTION.format(context=context_block)
    msgs: list[SystemMessage | HumanMessage | AIMessage] = [SystemMessage(content=full_system)]
    for msg in history:
        if msg.role == "user":
            msgs.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            msgs.append(AIMessage(content=msg.content))
        # system messages from client are intentionally ignored — server controls system prompt
    return msgs
