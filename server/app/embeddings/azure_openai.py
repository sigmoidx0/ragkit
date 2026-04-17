"""Azure OpenAI embeddings client."""

from __future__ import annotations

import httpx


class AzureOpenAIEmbedder:
    def __init__(
        self,
        endpoint: str,
        deployment: str,
        api_version: str,
        api_key: str | None,
        timeout: float = 60.0,
    ) -> None:
        if not endpoint or not deployment:
            raise ValueError("Azure OpenAI endpoint and deployment are required")
        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is required for Azure OpenAI")
        self._url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
            f"/embeddings?api-version={api_version}"
        )
        self._client = httpx.Client(
            timeout=timeout,
            headers={"api-key": api_key, "Content-Type": "application/json"},
        )

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        resp = self._client.post(self._url, json={"input": inputs})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") or []
        items = sorted(items, key=lambda d: d.get("index", 0))
        return [[float(x) for x in d["embedding"]] for d in items]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]
