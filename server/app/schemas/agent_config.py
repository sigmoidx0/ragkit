"""Per-agent configuration, stored as JSON on `services.agent_config`.

A Service is presented as an Agent in the UI. Everything a user can tune about
how that agent answers lives here: its card on the landing page, which model it
runs on, how it retrieves, and which routes its supervisor may pick. API keys
never live here — they stay in environment variables (see app/agent/config.py).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import LlmProvider

RouteName = Literal["retrieval", "summary", "comparison", "direct"]
RetrievalMode = Literal["on", "off", "auto"]
Accent = Literal["teal", "blue", "purple", "amber", "rose", "slate"]

# What the supervisor reads when choosing a route. Users can rewrite these to
# steer routing for their own domain without touching code.
DEFAULT_ROUTE_DESCRIPTIONS: dict[str, str] = {
    "retrieval": "factual questions, definitions, explanations",
    "summary": "requests to summarize a topic or document",
    "comparison": "requests to compare, contrast, or differentiate items",
    "direct": "greetings or small talk that clearly need no document lookup",
}

ROUTE_ORDER: tuple[str, ...] = ("retrieval", "summary", "comparison", "direct")


class AgentRouteConfig(BaseModel):
    enabled: bool = True
    description: str = Field(default="", max_length=300)


class AgentLlmConfig(BaseModel):
    """Overrides on top of `config.yaml`'s `llm` section. None means inherit."""

    provider: LlmProvider | None = None
    model: str | None = Field(default=None, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class AgentConfig(BaseModel):
    # ── Presentation: what the landing card and chat header show ──
    description: str = Field(default="", max_length=500)
    # None keeps the UI's name-based theme, so agents created before this
    # setting existed look the same until someone picks.
    icon: str | None = Field(default=None, max_length=8)
    accent: Accent | None = None
    starter_questions: list[str] = Field(default_factory=list, max_length=6)

    # ── Model ──
    llm: AgentLlmConfig = Field(default_factory=AgentLlmConfig)

    # ── Retrieval ──
    # None uses the built-in search chain; otherwise an *active* pipeline built
    # in the Pipeline Builder for this agent.
    pipeline_id: int | None = None
    # None inherits config.yaml (chat.default_top_k / agent.max_iterations), the
    # same rule the llm block follows.
    top_k: int | None = Field(default=None, ge=1, le=50)
    max_iterations: int | None = Field(default=None, ge=1, le=10)
    default_retrieval_mode: RetrievalMode = "auto"

    # ── Delegation ──
    # Other agents this one may consult as tools (one level deep; see
    # app/agent/delegation.py). Ignored for any the chatting user can't access.
    delegates: list[int] = Field(default_factory=list, max_length=5)

    # ── Router ──
    # validate_default so an agent with no stored config still gets all four
    # routes filled in — Pydantic skips validators on defaults otherwise.
    routes: dict[RouteName, AgentRouteConfig] = Field(default_factory=dict, validate_default=True)

    @field_validator("starter_questions")
    @classmethod
    def _drop_blank_questions(cls, value: list[str]) -> list[str]:
        return [q.strip() for q in value if q.strip()]

    @field_validator("routes")
    @classmethod
    def _fill_routes(cls, value: dict[str, AgentRouteConfig]) -> dict[str, AgentRouteConfig]:
        """Always carry all four routes, in a stable order, with a description."""
        filled: dict[str, AgentRouteConfig] = {}
        for name in ROUTE_ORDER:
            route = value.get(name) or AgentRouteConfig()
            if not route.description.strip():
                route = route.model_copy(update={"description": DEFAULT_ROUTE_DESCRIPTIONS[name]})
            filled[name] = route
        return filled

    @classmethod
    def from_stored(cls, raw: dict | None) -> AgentConfig:
        """Parse the stored JSON, treating a missing or empty value as defaults."""
        return cls.model_validate(raw or {})

    def active_routes(self, retrieval_mode: RetrievalMode) -> list[str]:
        """Routes the supervisor may choose from for one request.

        The chat's retrieval toggle narrows the configured set: "off" means
        answer directly, "on" means always consult documents.
        """
        if retrieval_mode == "off":
            return ["direct"]
        enabled = [name for name in ROUTE_ORDER if self.routes[name].enabled]
        if retrieval_mode == "on":
            enabled = [name for name in enabled if name != "direct"]
        # A config that leaves nothing reachable still has to answer something.
        return enabled or ["retrieval"]
