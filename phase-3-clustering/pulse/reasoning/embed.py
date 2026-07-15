"""Embeddings for clustering (architecture §6).

The embedder is abstracted so backends can be swapped without touching clustering:

  - HashingEmbedder            — dependency-light (numpy only), fully deterministic, offline.
                                 The default; good for tests and a reasonable pilot baseline.
  - SentenceTransformerEmbedder — semantic embeddings (optional, lazy; pulls in torch).

A CachingEmbedder wraps any backend so repeated text embeds are served from cache and return
identical vectors (eval E3.1). No generative LLM is involved at this stage.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

_WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray:  # (n, dim) float32
        ...


def _tokens(text: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return words + bigrams


class HashingEmbedder:
    """Deterministic feature-hashing embedder (the hashing trick) with L2 normalization."""

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in _tokens(text):
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if (h[4] & 1) else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([self._embed_one(t) for t in texts])


class SentenceTransformerEmbedder:
    """Semantic embeddings via sentence-transformers (optional, lazy import)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        model = self._load()
        return np.asarray(model.encode(texts, normalize_embeddings=True), dtype=np.float32)


class CachingEmbedder:
    """Wraps a backend, caching per-text vectors so repeated texts return identical vectors."""

    def __init__(self, backend: Embedder):
        self.backend = backend
        self._cache: dict[str, np.ndarray] = {}

    def embed(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in texts if t not in self._cache]
        if missing:
            # De-duplicate while preserving order for the backend call.
            unique = list(dict.fromkeys(missing))
            vectors = self.backend.embed(unique)
            for t, v in zip(unique, vectors):
                self._cache[t] = v
        return np.vstack([self._cache[t] for t in texts]) if texts else self.backend.embed([])


def build_embedder(settings) -> CachingEmbedder:
    """Construct the configured embedder (wrapped in a cache)."""
    cfg = settings.reasoning
    if cfg.embedder == "sentence-transformers":
        backend: Embedder = SentenceTransformerEmbedder(cfg.embedding_model)
    else:
        backend = HashingEmbedder(dim=cfg.embedding_dim)
    return CachingEmbedder(backend)
