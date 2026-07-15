"""Density clustering + ranking (architecture §6).

Pipeline: embeddings -> UMAP (dimensionality reduction) -> HDBSCAN (density clusters) ->
rank by size x recency x rating-spread. HDBSCAN noise (label -1) is discarded.

A deterministic, dependency-light fallback (cosine-threshold connected components) is used when
UMAP/HDBSCAN are unavailable or the corpus is too small for them, so the agent still runs and
tests stay reproducible. No generative LLM is used here.
"""

from __future__ import annotations

import logging

import numpy as np

from pulse.models import Cluster
from pulse.reasoning.embed import Embedder, build_embedder

logger = logging.getLogger("pulse.reasoning.cluster")

_NOISE = -1


def _umap_hdbscan_available() -> bool:
    try:
        import hdbscan  # noqa: F401
        import umap  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _labels_umap_hdbscan(embeddings: np.ndarray, cfg) -> np.ndarray:
    import hdbscan
    import umap

    n = embeddings.shape[0]
    n_neighbors = max(2, min(cfg.umap_neighbors, n - 1))
    n_components = max(2, min(cfg.umap_components, n - 2))
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=n_neighbors,
        metric="cosine",
        random_state=cfg.random_seed,
    )
    reduced = reducer.fit_transform(embeddings)
    clusterer = hdbscan.HDBSCAN(min_cluster_size=cfg.min_cluster_size, metric="euclidean")
    return clusterer.fit_predict(reduced)


def _labels_fallback(embeddings: np.ndarray, cfg) -> np.ndarray:
    """Cosine-threshold connected components via union-find (deterministic)."""
    n = embeddings.shape[0]
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # Embeddings are L2-normalized, so dot product == cosine similarity.
    sim = embeddings @ embeddings.T
    thr = cfg.fallback_similarity_threshold
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= thr:
                union(i, j)

    # Components below min_cluster_size become noise.
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    labels = np.full(n, _NOISE, dtype=int)
    next_label = 0
    for _root, members in sorted(groups.items()):
        if len(members) >= cfg.min_cluster_size:
            for i in members:
                labels[i] = next_label
            next_label += 1
    return labels


def _choose_backend(cfg, n: int) -> str:
    mode = cfg.clusterer
    if mode == "fallback":
        return "fallback"
    if mode == "umap_hdbscan":
        if not _umap_hdbscan_available():
            raise RuntimeError("clusterer=umap_hdbscan but umap-learn/hdbscan are not installed")
        return "umap_hdbscan"
    # auto: prefer UMAP+HDBSCAN when available and the corpus is large enough.
    if n >= max(cfg.min_reviews_for_clustering, 10) and _umap_hdbscan_available():
        return "umap_hdbscan"
    return "fallback"


def _rank(labels: np.ndarray, ratings: list[int], times: list[float], ids: list[str]) -> list[Cluster]:
    groups: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        if lab != _NOISE:
            groups.setdefault(int(lab), []).append(i)
    if not groups:
        return []

    raw = []
    for lab, idxs in groups.items():
        r = np.array([ratings[i] for i in idxs], dtype=float)
        t = np.array([times[i] for i in idxs], dtype=float)
        raw.append(
            {
                "review_ids": sorted(ids[i] for i in idxs),
                "size": len(idxs),
                "avg_rating": float(r.mean()),
                "spread": float(r.std()),
                "recency": float(t.max()),
            }
        )

    def _norm(values: list[float]) -> list[float]:
        lo, hi = min(values), max(values)
        if hi - lo < 1e-12:
            return [0.5] * len(values)
        return [(v - lo) / (hi - lo) for v in values]

    rec_norm = _norm([c["recency"] for c in raw])
    spread_norm = _norm([c["spread"] for c in raw])

    clusters: list[Cluster] = []
    for c, rn, sn in zip(raw, rec_norm, spread_norm):
        score = c["size"] * (0.5 + 0.5 * rn) * (0.5 + 0.5 * sn)
        clusters.append(
            Cluster(
                cluster_id=0,
                review_ids=c["review_ids"],
                size=c["size"],
                score=round(score, 6),
                avg_rating=round(c["avg_rating"], 4),
            )
        )

    # Rank: score desc, then size desc, then first review id for stable ordering.
    clusters.sort(key=lambda c: (-c.score, -c.size, c.review_ids[0]))
    for rank, c in enumerate(clusters):
        c.cluster_id = rank
    return clusters


def cluster_reviews(reviews, settings, embedder: Embedder | None = None) -> list[Cluster]:
    """Cluster reviews and return clusters ranked best-first (empty if low-signal)."""
    cfg = settings.reasoning
    n = len(reviews)
    if n < cfg.min_reviews_for_clustering:
        logger.info("only %d reviews (< %d) — low signal, skipping clustering", n, cfg.min_reviews_for_clustering)
        return []

    embedder = embedder or build_embedder(settings)
    texts = [r.body_clean for r in reviews]
    embeddings = np.asarray(embedder.embed(texts), dtype=np.float32)

    backend = _choose_backend(cfg, n)
    logger.info("clustering %d reviews via %s", n, backend)
    if backend == "umap_hdbscan":
        labels = _labels_umap_hdbscan(embeddings, cfg)
    else:
        labels = _labels_fallback(embeddings, cfg)

    ratings = [int(r.rating) for r in reviews]
    times = [r.posted_at.timestamp() for r in reviews]
    ids = [r.review_id for r in reviews]
    return _rank(labels, ratings, times, ids)
