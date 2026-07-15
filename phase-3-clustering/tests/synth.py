"""Synthetic labeled review data for clustering tests.

Three themes, each built from a strong shared keyword core plus one unique filler word per
review. The dominant shared vocabulary means even a purely lexical embedder (the hashing
backend used in deterministic tests) groups a theme together while keeping themes apart.
Returns CleanReview objects plus gold theme labels (aligned by index).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pulse.models import CleanReview

_CORES = {
    0: "the app crashes freezes and lags badly during trading orders every session",
    1: "customer support is slow unhelpful and never resolves my support ticket issue",
    2: "the navigation interface is confusing and lacks advanced analytics charts reporting",
}

_RATING_CYCLE = {0: [1, 2], 1: [2, 3], 2: [3, 4]}

_FILLERS = [
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "xi", "omicron", "pi", "rho",
    "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega",
]


def build_themed_reviews(repeats: int = 3):
    """Build `repeats * 5` reviews per theme (45 total at repeats=3)."""
    per_theme = repeats * 5
    reviews: list[CleanReview] = []
    gold: list[int] = []
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    counter = 0
    for theme, core in _CORES.items():
        for i in range(per_theme):
            body = f"{core} {_FILLERS[i % len(_FILLERS)]}"
            reviews.append(
                CleanReview(
                    source="app_store",
                    product_id="groww",
                    review_id=f"r{counter:03d}",
                    rating=_RATING_CYCLE[theme][i % 2],
                    body=body,
                    locale="in",
                    posted_at=base + timedelta(days=counter),
                    body_clean=body,
                    lang="en",
                )
            )
            gold.append(theme)
            counter += 1
    return reviews, gold


def predicted_labels(reviews, clusters) -> list[int]:
    """Map each review (by order) to its predicted cluster id, or -1 for noise."""
    id_to_cluster = {}
    for c in clusters:
        for rid in c.review_ids:
            id_to_cluster[rid] = c.cluster_id
    return [id_to_cluster.get(r.review_id, -1) for r in reviews]
