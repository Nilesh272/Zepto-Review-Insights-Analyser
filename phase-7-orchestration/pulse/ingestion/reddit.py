"""Reddit discussion ingestion (public JSON search — no API key required for read).

Collects posts (and top-level flavour) mentioning the product across configured
subreddits / site-wide queries, then maps them into ``RawReview`` so the rest of
the Pulse pipeline (scrub → cluster → insights) stays unchanged.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from pulse.ingestion.cache import RawCache
from pulse.models import RawReview
from pulse.utils.retry import with_retries

logger = logging.getLogger("pulse.ingestion.reddit")

HttpGet = Callable[[str], bytes]

_USER_AGENT = "pulse-review-insights/0.7 (research; local agent)"


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — controlled URLs
        return resp.read()


def _proxy_rating(*, score: int, upvote_ratio: float | None) -> int:
    """Map Reddit engagement to a 1–5 proxy so sentiment balancing still works."""
    if upvote_ratio is not None:
        if upvote_ratio >= 0.85:
            return 5
        if upvote_ratio >= 0.7:
            return 4
        if upvote_ratio >= 0.45:
            return 3
        if upvote_ratio >= 0.25:
            return 2
        return 1
    if score >= 80:
        return 5
    if score >= 20:
        return 4
    if score >= 5:
        return 3
    if score >= 1:
        return 2
    return 1


def parse_reddit_listing(payload: dict | list, product_id: str, *, query: str = "") -> list[RawReview]:
    """Parse a Reddit listing JSON into RawReview rows (source=reddit)."""
    if isinstance(payload, list):
        # Comment/post permalink responses are arrays; take the first listing.
        payload = payload[0] if payload and isinstance(payload[0], dict) else {}
    data = payload.get("data") if isinstance(payload, dict) else None
    children = (data or {}).get("children") or []
    out: list[RawReview] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        d = child.get("data") or {}
        if d.get("stickied"):
            continue
        rid = str(d.get("id") or "").strip()
        title = (d.get("title") or "").strip()
        selftext = (d.get("selftext") or "").strip()
        if selftext in ("[removed]", "[deleted]"):
            selftext = ""
        body = f"{title}\n\n{selftext}".strip() if selftext else title
        if not rid or not body or len(body.split()) < 4:
            continue
        created = d.get("created_utc")
        try:
            posted = datetime.fromtimestamp(float(created), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            continue
        sub = str(d.get("subreddit") or "reddit")
        author = d.get("author")
        score = int(d.get("score") or 0)
        ratio = d.get("upvote_ratio")
        try:
            ratio_f = float(ratio) if ratio is not None else None
        except (TypeError, ValueError):
            ratio_f = None
        out.append(
            RawReview(
                source="reddit",
                product_id=product_id,
                review_id=f"reddit:{sub}:{rid}",
                rating=_proxy_rating(score=score, upvote_ratio=ratio_f),
                title=title or None,
                body=body,
                author=None if not author or author in ("[deleted]", "AutoModerator") else str(author),
                locale=f"r/{sub}",
                posted_at=posted,
                app_version=None,
            )
        )
    return out


def fetch_reddit_discussions(
    product_id: str,
    *,
    queries: list[str],
    subreddits: list[str] | None = None,
    max_posts: int = 200,
    http_get: HttpGet | None = None,
    cache: RawCache | None = None,
    offline: bool = False,
    max_retries: int = 3,
    retry_backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> list[RawReview]:
    """Search Reddit for product discussions; dedupe by review_id; cap at ``max_posts``."""
    getter = http_get or _default_http_get
    q_list = [q.strip() for q in queries if q and str(q).strip()]
    if not q_list:
        return []
    subs = [s.strip().lstrip("r/") for s in (subreddits or []) if s and str(s).strip()]

    by_id: dict[str, RawReview] = {}

    def _search(url: str, cache_key: str) -> list[dict]:
        payload = cache.get("reddit", product_id, cache_key) if cache else None
        if payload is None:
            if offline:
                return []
            def _do() -> dict:
                raw = getter(url)
                return json.loads(raw.decode("utf-8"))

            kwargs = {"max_retries": max_retries, "backoff_seconds": retry_backoff_seconds}
            if sleep is not None:
                kwargs["sleep"] = sleep
            try:
                payload = with_retries(_do, label=f"reddit:{cache_key}", **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("reddit fetch failed for %s (%s): %s", product_id, cache_key, exc)
                return []
            if cache:
                cache.put("reddit", product_id, cache_key, payload)
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [p for p in payload if isinstance(p, dict)]
        return []

    targets: list[tuple[str, str, str]] = []
    for q in q_list:
        enc = urllib.parse.quote_plus(q)
        if subs:
            for sub in subs:
                url = (
                    f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/search.json"
                    f"?q={enc}&restrict_sr=1&sort=new&limit=100&raw_json=1"
                )
                targets.append((url, f"{sub}_{enc[:40]}", q))
        else:
            url = (
                f"https://www.reddit.com/search.json"
                f"?q={enc}&sort=new&limit=100&raw_json=1"
            )
            targets.append((url, f"site_{enc[:48]}", q))

    for url, key, q in targets:
        for listing in _search(url, key):
            for rev in parse_reddit_listing(listing, product_id, query=q):
                by_id.setdefault(rev.review_id, rev)
        if len(by_id) >= max_posts:
            break

    reviews = list(by_id.values())
    reviews.sort(key=lambda r: r.posted_at, reverse=True)
    reviews = reviews[:max_posts]
    logger.info("reddit: fetched %d discussions for %s", len(reviews), product_id)
    return reviews
