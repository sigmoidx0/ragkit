"""vLLM OpenAI-compatible embeddings client."""

from __future__ import annotations

import httpx


class VllmEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not base_url or not model:
            raise ValueError("vLLM base_url and model are required")
        self._base = base_url.rstrip("/")
        self._model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        resp = self._client.post(
            f"{self._base}/embeddings", json={"model": self._model, "input": inputs}
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or []
        # Preserve original input ordering.
        items = sorted(items, key=lambda d: d.get("index", 0))
        return [[float(x) for x in d["embedding"]] for d in items]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]
