"""Text → vector.

Model: BAAI/bge-small-en-v1.5 via fastembed (ONNX Runtime, CPU).
  - Runs locally: no API key, no per-token cost, no data leaving the box.
  - 384 dims / ~130 MB: small enough to embed the whole real corpus on a
    laptop in about a minute, and to keep resident in the API process.
  - fastembed instead of sentence-transformers avoids pulling in PyTorch
    (~1 GB+ in the Docker image) just to run inference.

Asymmetric retrieval: BGE was trained with an instruction prefix on the
*query* side only ("Represent this sentence for searching relevant
passages: "). fastembed's query_embed() adds it; embed() doesn't. Queries
and passages must go through the matching method, or recall drops.

Vectors come back L2-normalized, so cosine similarity == dot product.
"""
import os
import threading
from typing import Protocol

import numpy as np

from db.models import EMBED_DIM

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")


class Embedder(Protocol):
    model_name: str

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedder:
    def __init__(self, model_name: str = EMBED_MODEL, batch_size: int = 64):
        from fastembed import TextEmbedding  # heavy import — only when used
        self.model_name = model_name
        self._model = TextEmbedding(model_name)
        self._batch_size = batch_size

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        vecs = np.array(list(self._model.embed(texts, batch_size=self._batch_size)), dtype=np.float32)
        if vecs.size and vecs.shape[1] != EMBED_DIM:
            raise ValueError(f"{self.model_name} returns {vecs.shape[1]} dims; schema expects {EMBED_DIM}")
        return vecs

    def embed_query(self, text: str) -> np.ndarray:
        return np.array(next(iter(self._model.query_embed(text))), dtype=np.float32)


_embedder = None
_lock = threading.Lock()


def get_embedder() -> Embedder:
    """Process-wide singleton, loaded on first use: the first RAG request
    pays ~1s of model load, but API startup and every non-RAG code path
    (tests, scraper, benchmark) never do."""
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = FastEmbedEmbedder()
    return _embedder
