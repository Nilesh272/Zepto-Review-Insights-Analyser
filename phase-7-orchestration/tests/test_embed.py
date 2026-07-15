"""E3.1/E3.2 — embedding determinism, caching, batching, and similarity structure."""

import numpy as np

from pulse.config import Settings
from pulse.reasoning.embed import CachingEmbedder, HashingEmbedder, build_embedder


def test_hashing_deterministic_and_normalized():
    e = HashingEmbedder(dim=128)
    a = e.embed(["the app crashes during trading"])
    b = e.embed(["the app crashes during trading"])
    assert np.array_equal(a, b)
    assert a.shape == (1, 128)
    assert abs(np.linalg.norm(a[0]) - 1.0) < 1e-5


def test_batching_shape():
    e = HashingEmbedder(dim=64)
    out = e.embed(["one two three", "four five six", "seven eight nine"])
    assert out.shape == (3, 64)


def test_similar_more_similar_than_different():
    e = HashingEmbedder(dim=512)
    v = e.embed([
        "the app crashes and freezes during trading hours",
        "it keeps crashing and freezing while trading",
        "customer support never replies to my tickets",
    ])
    sim_same = float(v[0] @ v[1])
    sim_diff = float(v[0] @ v[2])
    assert sim_same > sim_diff


def test_caching_serves_repeats(monkeypatch):
    calls = {"n": 0}

    class Counting(HashingEmbedder):
        def embed(self, texts):
            calls["n"] += len(texts)
            return super().embed(texts)

    cached = CachingEmbedder(Counting(dim=32))
    cached.embed(["a b c", "d e f"])
    cached.embed(["a b c"])  # served from cache
    assert calls["n"] == 2  # only the two unique texts ever hit the backend


def test_build_embedder_default_is_hashing():
    emb = build_embedder(Settings())
    assert isinstance(emb, CachingEmbedder)
    assert isinstance(emb.backend, HashingEmbedder)
