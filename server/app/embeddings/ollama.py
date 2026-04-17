"""Ollama embeddings via its native HTTP API."""

from __future__ import annotations

import httpx


class OllamaEmbedder:
    def __init__(self, base_url: str, model: str, timeout: float = 60.0) -> None:
        self._base = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=timeout)

    def _embed_one(self, text: str) -> list[float]:
        resp = self._client.post(
            f"{self._base}/api/embeddings",
            json={"model": self._model, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        vec = data.get("embedding")
        if not isinstance(vec, list):
            raise RuntimeError(f"unexpected ollama response: {data!r}")
        return [float(x) for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)
