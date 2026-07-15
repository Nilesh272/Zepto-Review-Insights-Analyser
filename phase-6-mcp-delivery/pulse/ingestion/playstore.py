"""Google Play ingestion (architecture §3.2).

Live fetching uses the optional `google-play-scraper` package; it is imported lazily so the
module (and the parser) can be unit-tested against fixtures without the dependency or network.
Raw entries are normalized to JSON-serializable dicts (datetimes -> ISO strings) so they can be
cached and replayed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from pulse.ingestion.cache import RawCache
from pulse.models import RawReview
from pulse.utils.retry import with_retries

logger = logging.getLogger("pulse.ingestion.playstore")

# A fetcher returns a list of JSON-serializable raw review dicts for a package.
PlayFetcher = Callable[[str, str, str, int], list[dict]]


def _coerce_dt(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_play_entries(entries: list[dict], product_id: str, *, locale: str = "en") -> list[RawReview]:
    """Map raw Google Play review dicts to RawReview objects."""
    reviews: list[RawReview] = []
    for e in entries:
        score = e.get("score")
        if score is None:
            continue
        try:
            reviews.append(
                RawReview(
                    source="play_store",
                    product_id=product_id,
                    review_id=str(e.get("reviewId") or e.get("review_id") or ""),
                    rating=int(score),
                    title=None,
                    body=e.get("content") or "",
                    author=e.get("userName"),
                    locale=locale,
                    posted_at=_coerce_dt(e.get("at")),
                    app_version=e.get("appVersion") or e.get("reviewCreatedVersion"),
                )
            )
        except (ValueError, TypeError) as exc:
            logger.warning("skipping malformed Play entry: %s", exc)
    return reviews


def _default_play_fetcher(package: str, lang: str, country: str, count: int) -> list[dict]:
    """Live fetch via google-play-scraper, returning JSON-serializable dicts."""
    try:
        from google_play_scraper import Sort, reviews as gp_reviews
    except ImportError as exc:  # pragma: no cover - exercised only without the optional dep
        raise RuntimeError(
            "google-play-scraper is not installed; install it for live Play fetching "
            "or run with offline cache."
        ) from exc

    collected: list[dict] = []
    token = None
    while len(collected) < count:
        batch, token = gp_reviews(
            package,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,
            count=min(200, count - len(collected)),
            continuation_token=token,
        )
        if not batch:
            break
        for r in batch:
            at = r.get("at")
            collected.append(
                {
                    "reviewId": r.get("reviewId"),
                    "userName": r.get("userName"),
                    "score": r.get("score"),
                    "content": r.get("content"),
                    "at": at.isoformat() if isinstance(at, datetime) else at,
                    "appVersion": r.get("appVersion") or r.get("reviewCreatedVersion"),
                }
            )
        if token is None:
            break
    return collected[:count]


def fetch_play_reviews(
    package: str,
    product_id: str,
    *,
    lang: str = "en",
    country: str = "in",
    count: int = 400,
    fetcher: PlayFetcher | None = None,
    cache: RawCache | None = None,
    offline: bool = False,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> list[RawReview]:
    """Fetch (or replay cached) Play reviews and parse them to RawReview objects."""
    key = f"{lang}_{country}_n{count}"
    payload = cache.get("play_store", product_id, key) if cache else None

    if payload is None:
        if offline:
            return []
        fetcher = fetcher or _default_play_fetcher

        def _do_fetch() -> list[dict]:
            return fetcher(package, lang, country, count)

        kwargs = {"max_retries": max_retries, "backoff_seconds": retry_backoff_seconds}
        if sleep is not None:
            kwargs["sleep"] = sleep
        payload = with_retries(_do_fetch, label="play_store", **kwargs)
        if cache:
            cache.put("play_store", product_id, key, payload)

    reviews = parse_play_entries(payload, product_id, locale=lang)
    logger.info("play_store: fetched %d reviews for %s", len(reviews), product_id)
    return reviews
