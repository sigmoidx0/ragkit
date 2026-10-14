"""Gemini chat model, spoken over its OpenAI-compatible endpoint.

Gemini is reachable two ways. The native `generateContent` API is the one
`langchain-google-genai` calls, but the current Gemini 3 models are served
through Google's newer Interactions API instead, so that integration cannot
reach them. The OpenAI-compatible endpoint can, which lets `ChatOpenAI` do all
the real work here.

One Gemini quirk needs bridging. Gemini 3 issues a `thought_signature` with
every tool call and rejects the next turn unless that signature is echoed back
alongside the function call it belongs to:

    400 INVALID_ARGUMENT — Function call is missing a thought_signature in
    functionCall parts. This is required for tools to work correctly.

The signature travels in a non-standard `extra_content` field that
`langchain-openai` drops on the floor, which breaks any agent that calls a tool
and then keeps talking. `ChatGemini` captures the signature off each response
and re-attaches it to the matching assistant message on the way back out.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.outputs import ChatResult
from langchain_openai import ChatOpenAI

# Parked in `additional_kwargs` under a private key. `langchain-openai` copies
# only keys it recognizes into outgoing requests, so this never leaks upstream.
_SIGNATURE_KEY = "__gemini_thought_signature"


def _signature_of(message: dict) -> str | None:
    """Pull the thought signature out of a raw response message, if present."""
    google = (message.get("extra_content") or {}).get("google") or {}
    return google.get("thought_signature")


class ChatGemini(ChatOpenAI):
    """`ChatOpenAI` that round-trips Gemini's `thought_signature`."""

    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        raw = response if isinstance(response, dict) else response.model_dump()
        for generation, choice in zip(result.generations, raw.get("choices") or [], strict=True):
            signature = _signature_of(choice.get("message") or {})
            if signature:
                generation.message.additional_kwargs[_SIGNATURE_KEY] = signature
        return result

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        # Signatures are keyed by tool-call id so they survive any reordering or
        # trimming the agent does to the history between turns.
        by_tool_call_id: dict[str, str] = {}
        for message in self._convert_input(input_).to_messages():
            signature = getattr(message, "additional_kwargs", {}).get(_SIGNATURE_KEY)
            if not signature:
                continue
            for call in getattr(message, "tool_calls", None) or []:
                if call.get("id"):
                    by_tool_call_id[call["id"]] = signature

        if not by_tool_call_id:
            return payload

        for message_dict in payload.get("messages") or []:
            signature = next(
                (
                    by_tool_call_id[call["id"]]
                    for call in message_dict.get("tool_calls") or []
                    if call.get("id") in by_tool_call_id
                ),
                None,
            )
            if signature:
                message_dict["extra_content"] = {
                    "google": {"thought_signature": signature}
                }
        return payload
