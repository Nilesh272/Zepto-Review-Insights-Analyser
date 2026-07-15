"""Real UMAP + HDBSCAN backend (architecture §6). Skipped if the libs aren't installed."""

import pytest

from pulse.config import Settings
from pulse.reasoning.cluster import _umap_hdbscan_available, cluster_reviews
from tests.synth import build_themed_reviews

pytestmark = pytest.mark.skipif(
    not _umap_hdbscan_available(), reason="umap-learn/hdbscan not installed"
)


def _settings():
    return Settings(reasoning={"clusterer": "umap_hdbscan", "min_cluster_size": 3, "random_seed": 42})


def test_umap_hdbscan_finds_clusters():
    reviews, _ = build_themed_reviews(repeats=4)  # 60 reviews
    clusters = cluster_reviews(reviews, _settings())
    assert len(clusters) >= 1
    assert all(c.size >= 3 for c in clusters)


def test_umap_hdbscan_is_reproducible():
    reviews, _ = build_themed_reviews(repeats=4)
    a = cluster_reviews(reviews, _settings())
    b = cluster_reviews(reviews, _settings())
    assert [(c.cluster_id, tuple(c.review_ids)) for c in a] == [
        (c.cluster_id, tuple(c.review_ids)) for c in b
    ]
