"""HuggingFace Text Embeddings Inference (TEI) client."""

from __future__ import annotations

import httpx


class TeiEmbedder:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 60.0) -> None:
        if not base_url:
            raise ValueError("TEI base_url is required")
        self._base = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        resp = self._client.post(f"{self._base}/embed", json={"inputs": inputs})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise RuntimeError(f"unexpected TEI response: {data!r}")
        return [[float(x) for x in vec] for vec in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed([text])
        return vectors[0]
