"""E3.3-E3.8 — clustering quality, ranking, determinism, and edge cases (fallback backend)."""

from datetime import datetime, timezone

from sklearn.metrics import adjusted_rand_score

from pulse.config import Settings
from pulse.models import CleanReview
from pulse.reasoning.cluster import cluster_reviews
from tests.synth import build_themed_reviews, predicted_labels


def _settings(**reasoning):
    base = {"clusterer": "fallback", "min_cluster_size": 3, "min_reviews_for_clustering": 5}
    base.update(reasoning)
    return Settings(reasoning=base)


def test_recovers_three_themes_ari():
    reviews, gold = build_themed_reviews(repeats=3)  # 45 reviews, 3 themes
    clusters = cluster_reviews(reviews, _settings())
    assert len(clusters) == 3
    ari = adjusted_rand_score(gold, predicted_labels(reviews, clusters))
    assert ari >= 0.6


def test_ranking_sorted_and_ids_sequential():
    reviews, _ = build_themed_reviews(repeats=3)
    clusters = cluster_reviews(reviews, _settings())
    scores = [c.score for c in clusters]
    assert scores == sorted(scores, reverse=True)
    assert [c.cluster_id for c in clusters] == list(range(len(clusters)))


def test_determinism():
    reviews, _ = build_themed_reviews(repeats=3)
    a = cluster_reviews(reviews, _settings())
    b = cluster_reviews(reviews, _settings())
    assert [(c.cluster_id, tuple(c.review_ids)) for c in a] == [
        (c.cluster_id, tuple(c.review_ids)) for c in b
    ]


def test_low_signal_returns_empty():
    # X3.1 — fewer than min_reviews_for_clustering.
    reviews, _ = build_themed_reviews(repeats=3)
    assert cluster_reviews(reviews[:4], _settings()) == []


def test_all_noise_returns_empty():
    # X3.2 — distinct one-off reviews, none similar enough to group.
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    reviews = [
        CleanReview(
            source="app_store", product_id="groww", review_id=f"n{i}", rating=3,
            body=body, locale="in", posted_at=base, body_clean=body, lang="en",
        )
        for i, body in enumerate([
            "alpha bravo charlie delta echo",
            "foxtrot golf hotel india juliet",
            "kilo lima mike november oscar",
            "papa quebec romeo sierra tango",
            "uniform victor whiskey xray yankee",
        ])
    ]
    assert cluster_reviews(reviews, _settings()) == []


def test_single_theme_one_cluster():
    # X3.3 — homogeneous corpus collapses to a single cluster.
    reviews, _ = build_themed_reviews(repeats=3)
    perf_only = [r for r, g in zip(reviews, build_themed_reviews(3)[1]) if g == 0]
    clusters = cluster_reviews(perf_only, _settings())
    assert len(clusters) == 1
    assert clusters[0].size == len(perf_only)
