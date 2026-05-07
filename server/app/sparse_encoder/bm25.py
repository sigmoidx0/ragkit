from __future__ import annotations

from app.sparse_encoder.base import SparseVector


class BM25Encoder:
    def __init__(self, model_name: str = "Qdrant/bm25") -> None:
        from fastembed import SparseTextEmbedding
        self._model = SparseTextEmbedding(model_name=model_name)

    def encode_documents(self, texts: list[str]) -> list[SparseVector]:
        return [
            SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
            for r in self._model.embed(texts)
        ]

    def encode_query(self, text: str) -> SparseVector:
        result = list(self._model.query_embed([text]))[0]
        return SparseVector(indices=result.indices.tolist(), values=result.values.tolist())
