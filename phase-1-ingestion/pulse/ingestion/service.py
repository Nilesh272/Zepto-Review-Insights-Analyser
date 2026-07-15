"""High-level ingestion orchestration for `fetch_reviews` (architecture §3.2, §4).

Computes the rolling window for a given ISO week, fetches both stores with per-source error
isolation (a failing source is recorded and skipped, not fatal — edge case X1.2/X1.3), then
normalizes + quality-filters into NormalizedReview[].
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable

from pydantic import BaseModel, Field

from pulse.config import Product, Settings
from pulse.ingestion.appstore import HttpGet, fetch_app_store_reviews
from pulse.ingestion.cache import RawCache
from pulse.ingestion.filters import Detector, default_detector
from pulse.ingestion.normalize import NormalizeStats, normalize_reviews
from pulse.ingestion.playstore import PlayFetcher, fetch_play_reviews
from pulse.models import NormalizedReview, RawReview
from pulse.utils.isoweek import IsoWeek

logger = logging.getLogger("pulse.ingestion.service")


class IngestionResult(BaseModel):
    reviews: list[NormalizedReview]
    stats: NormalizeStats
    source_counts: dict[str, int] = Field(default_factory=dict)
    source_errors: dict[str, str] = Field(default_factory=dict)
    window_start: str
    window_end: str


def compute_window(iso_week: IsoWeek, window_weeks: int) -> tuple:
    """Return (start, end) UTC datetimes for the rolling window ending at `iso_week`."""
    end = iso_week.sunday() + timedelta(days=1) - timedelta(microseconds=1)  # Sun 23:59:59.999
    start = iso_week.monday() - timedelta(weeks=window_weeks - 1)
    return start, end


def run_ingestion(
    product: Product,
    settings: Settings,
    iso_week: IsoWeek,
    *,
    cache: RawCache | None = None,
    offline: bool = False,
    detector: Detector | None = None,
    appstore_http_get: HttpGet | None = None,
    play_fetcher: PlayFetcher | None = None,
    sleep: Callable[[float], None] | None = None,
) -> IngestionResult:
    window_start, window_end = compute_window(iso_week, settings.window_weeks)
    ing = settings.ingestion

    raw: list[RawReview] = []
    source_counts: dict[str, int] = {}
    source_errors: dict[str, str] = {}

    # --- App Store (per-source isolation) ---
    try:
        app_reviews = fetch_app_store_reviews(
            product.app_store_id,
            product.id,
            country=ing.app_store_country,
            max_pages=ing.max_app_store_pages,
            http_get=appstore_http_get,
            cache=cache,
            offline=offline,
            max_retries=ing.max_retries,
            retry_backoff_seconds=ing.retry_backoff_seconds,
            sleep=sleep,
        )
        raw.extend(app_reviews)
        source_counts["app_store"] = len(app_reviews)
    except Exception as exc:  # noqa: BLE001 - isolate source failure
        source_errors["app_store"] = repr(exc)
        logger.warning("app_store ingestion failed for %s: %s", product.id, exc)

    # --- Google Play (per-source isolation) ---
    try:
        play_reviews = fetch_play_reviews(
            product.play_package,
            product.id,
            lang=ing.play_lang,
            country=ing.play_country,
            count=ing.max_play_reviews,
            fetcher=play_fetcher,
            cache=cache,
            offline=offline,
            max_retries=ing.max_retries,
            retry_backoff_seconds=ing.retry_backoff_seconds,
            sleep=sleep,
        )
        raw.extend(play_reviews)
        source_counts["play_store"] = len(play_reviews)
    except Exception as exc:  # noqa: BLE001 - isolate source failure
        source_errors["play_store"] = repr(exc)
        logger.warning("play_store ingestion failed for %s: %s", product.id, exc)

    detector = detector or default_detector()
    result = normalize_reviews(
        raw,
        settings=settings,
        window_start=window_start,
        window_end=window_end,
        detector=detector,
    )

    return IngestionResult(
        reviews=result.reviews,
        stats=result.stats,
        source_counts=source_counts,
        source_errors=source_errors,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
    )
