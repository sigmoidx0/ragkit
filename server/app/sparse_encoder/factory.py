from __future__ import annotations

from functools import lru_cache

from app.sparse_encoder.base import SparseEncoder
from app.sparse_encoder.bm25 import BM25Encoder


@lru_cache(maxsize=1)
def get_sparse_encoder() -> SparseEncoder:
    return BM25Encoder()


def reset_sparse_encoder_cache() -> None:
    get_sparse_encoder.cache_clear()
