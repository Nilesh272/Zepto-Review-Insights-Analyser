"""Apple App Store ingestion via the iTunes customer-reviews RSS JSON feed (architecture §3.2).

The feed is public (no auth). Parsing is separated from fetching so it can be unit-tested
against recorded fixtures without the network. The first feed `entry` is app metadata (it has
no `im:rating`) and is skipped.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from pulse.ingestion.cache import RawCache
from pulse.models import RawReview
from pulse.utils.retry import with_retries

logger = logging.getLogger("pulse.ingestion.appstore")

HttpGet = Callable[[str], str]

_FEED_URL = (
    "https://itunes.apple.com/{country}/rss/customerreviews/"
    "page={page}/id={app_id}/sortby=mostrecent/json"
)


def build_feed_url(app_id: str, country: str, page: int) -> str:
    return _FEED_URL.format(country=country.lower(), app_id=app_id, page=page)


def _default_http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "pulse-agent/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https host
        return resp.read().decode("utf-8")


def _label(node: dict, *keys: str):
    """Walk nested dicts pulling the final 'label' value, tolerating missing nodes."""
    cur = node
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    if isinstance(cur, dict):
        return cur.get("label")
    return cur


def _parse_updated(value: str | None) -> datetime:
    if not value:
        raise ValueError("App Store review missing 'updated' timestamp")
    # e.g. "2026-06-01T12:00:00-07:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_app_store_json(payload: dict | str, product_id: str, *, locale: str = "us") -> list[RawReview]:
    """Parse one RSS-feed JSON page into RawReview objects (skips the app-metadata entry)."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    feed = (payload or {}).get("feed", {})
    entries = feed.get("entry", [])
    if isinstance(entries, dict):  # single entry => app metadata only, no reviews
        entries = [entries]

    reviews: list[RawReview] = []
    for entry in entries:
        rating = _label(entry, "im:rating")
        if rating is None:
            continue  # app-metadata entry, not a review
        try:
            reviews.append(
                RawReview(
                    source="app_store",
                    product_id=product_id,
                    review_id=str(_label(entry, "id") or ""),
                    rating=int(rating),
                    title=_label(entry, "title"),
                    body=_label(entry, "content") or "",
                    author=_label(entry, "author", "name"),
                    locale=locale,
                    posted_at=_parse_updated(_label(entry, "updated")),
                    app_version=_label(entry, "im:version"),
                )
            )
        except (ValueError, TypeError) as exc:
            logger.warning("skipping malformed App Store entry: %s", exc)
    return reviews


def fetch_app_store_reviews(
    app_id: str,
    product_id: str,
    *,
    country: str = "in",
    max_pages: int = 10,
    http_get: HttpGet | None = None,
    cache: RawCache | None = None,
    offline: bool = False,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> list[RawReview]:
    """Page through the RSS feed (Apple caps at 10 pages) and return parsed reviews.

    With ``offline=True`` only cached pages are read (no network). Pagination stops when a page
    yields no reviews.
    """
    http_get = http_get or _default_http_get
    all_reviews: list[RawReview] = []

    for page in range(1, max_pages + 1):
        key = f"{country}_page{page}"
        payload = cache.get("app_store", product_id, key) if cache else None

        if payload is None:
            if offline:
                break  # nothing cached for this page; stop
            url = build_feed_url(app_id, country, page)

            def _do_get(u=url) -> str:
                return http_get(u)

            kwargs = {"max_retries": max_retries, "backoff_seconds": retry_backoff_seconds}
            if sleep is not None:
                kwargs["sleep"] = sleep
            raw = with_retries(_do_get, label=f"app_store p{page}", **kwargs)
            payload = json.loads(raw)
            if cache:
                cache.put("app_store", product_id, key, payload)

        page_reviews = parse_app_store_json(payload, product_id, locale=country)
        if not page_reviews:
            break
        all_reviews.extend(page_reviews)

    logger.info("app_store: fetched %d reviews for %s", len(all_reviews), product_id)
    return all_reviews
