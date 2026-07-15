"""Shared builders for Phase 7 orchestration tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pulse.agent.tools import build_default_registry
from pulse.config import Config, Limits, Product, ProductRegistry, Settings
from pulse.models import RawReview

_CORES = {
    "perf": "the app crashes freezes and lags badly during trading orders every session",
    "support": "customer support is slow unhelpful and never resolves my support ticket issue",
    "ux": "the navigation interface is confusing and lacks advanced analytics charts reporting",
}
_FILLERS = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron".split()


def build_raw_reviews(per_theme: int = 6) -> list[RawReview]:
    """Synthetic RawReviews with strong per-theme vocab so clustering recovers themes."""
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    reviews: list[RawReview] = []
    n = 0
    for core in _CORES.values():
        for i in range(per_theme):
            reviews.append(
                RawReview(
                    source="app_store", product_id="groww", review_id=f"r{n:03d}",
                    rating=1 + (i % 5), body=f"{core} {_FILLERS[i % len(_FILLERS)]}",
                    locale="in", posted_at=base + timedelta(days=n),
                )
            )
            n += 1
    return reviews


def make_config(*, products=None, email_mode="draft", max_tokens=200_000) -> Config:
    settings = Settings(email_mode=email_mode, limits=Limits(max_tokens_per_run=max_tokens))
    products = products or [
        Product(id="groww", name="Groww", app_store_id="1", play_package="com.groww",
                doc_id="doc-groww", recipients=["pulse@example.com"]),
    ]
    return Config(settings=settings, registry=ProductRegistry(products=products))


def seeded_registry(reviews: list[RawReview]):
    """Default registry with fetch_reviews replaced by an injector (no network)."""
    reg = build_default_registry()

    def _seed(ctx):
        ctx.bag["reviews"] = reviews
        return {"kept": len(reviews), "input_total": len(reviews), "source_counts": {}, "source_errors": {}}

    reg.get("fetch_reviews").fn = _seed
    return reg


def multi_product_config(ids: list[str]) -> Config:
    products = [
        Product(id=pid, name=pid.title(), app_store_id="1", play_package=f"com.{pid}",
                doc_id=f"doc-{pid}", recipients=["pulse@example.com"])
        for pid in ids
    ]
    return make_config(products=products)
