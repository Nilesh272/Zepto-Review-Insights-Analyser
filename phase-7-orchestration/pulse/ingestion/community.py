"""Community / social / forum file-drop ingestion.

Supports the research sources that are hard to scrape reliably without vendor APIs:
community forums, social posts, product reviews, and quick-commerce discussions.

Drop JSON/JSONL files under the configured directory. Each row:

  {
    "source": "forum" | "social" | "product_review" | "quick_commerce" | "reddit",
    "review_id": "unique-id",
    "body": "discussion text…",
    "posted_at": "2026-07-01T12:00:00+00:00",
    "rating": 1-5,          # optional; default 3
    "title": "...",         # optional
    "author": "...",        # optional
    "locale": "forum-name"  # optional
  }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pulse.models import RawReview

logger = logging.getLogger("pulse.ingestion.community")

_ALLOWED: set[str] = {
    "forum",
    "social",
    "product_review",
    "quick_commerce",
    "reddit",
}


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_review(row: dict, product_id: str, *, default_source: str) -> RawReview | None:
    src = str(row.get("source") or default_source).strip().lower()
    if src not in _ALLOWED:
        src = default_source if default_source in _ALLOWED else "forum"
    body = str(row.get("body") or row.get("text") or "").strip()
    rid = str(row.get("review_id") or row.get("id") or "").strip()
    if not body or not rid:
        return None
    posted = _parse_dt(row.get("posted_at") or row.get("created_at"))
    if posted is None:
        return None
    rating_raw = row.get("rating", 3)
    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = 3
    rating = max(1, min(5, rating))
    return RawReview(
        source=src,  # type: ignore[arg-type]
        product_id=product_id,
        review_id=f"{src}:{rid}" if ":" not in rid else rid,
        rating=rating,
        title=(str(row["title"]).strip() if row.get("title") else None),
        body=body,
        author=(str(row["author"]).strip() if row.get("author") else None),
        locale=str(row.get("locale") or src),
        posted_at=posted,
        app_version=None,
    )


def load_community_drop_file(path: Path, product_id: str) -> list[RawReview]:
    """Load one JSON array or JSONL file of community discussion rows."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    default_source = "forum"
    name = path.stem.lower()
    for key in _ALLOWED:
        if key in name:
            default_source = key
            break

    rows: list[dict] = []
    if path.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    else:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("skipping unreadable community drop %s", path)
            return []
        if isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)]
        elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
            rows = [r for r in payload["items"] if isinstance(r, dict)]
        elif isinstance(payload, dict):
            rows = [payload]

    out: list[RawReview] = []
    for row in rows:
        rev = _row_to_review(row, product_id, default_source=default_source)
        if rev:
            out.append(rev)
    return out


def fetch_community_file_drops(
    product_id: str,
    *,
    drop_dir: str | Path,
) -> list[RawReview]:
    """Load all JSON/JSONL drops for a product (optional ``<product_id>/`` subfolder first)."""
    root = Path(drop_dir)
    if not root.is_dir():
        return []
    candidates = [
        *sorted((root / product_id).glob("*.json")),
        *sorted((root / product_id).glob("*.jsonl")),
        *sorted(root.glob("*.json")),
        *sorted(root.glob("*.jsonl")),
    ]
    # Prefer product subfolder files; also allow root shared files.
    seen_paths: set[Path] = set()
    by_id: dict[str, RawReview] = {}
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        for rev in load_community_drop_file(path, product_id):
            by_id.setdefault(rev.review_id, rev)
    reviews = list(by_id.values())
    logger.info("community drops: loaded %d rows for %s from %s", len(reviews), product_id, root)
    return reviews


def ensure_drop_dir_examples(drop_dir: str | Path, product_id: str = "zepto") -> Path:
    """Create the drop directory with a sample file if empty (dev convenience)."""
    root = Path(drop_dir) / product_id
    root.mkdir(parents=True, exist_ok=True)
    sample = root / "example_forum_social.json"
    if not sample.exists() and not any(root.glob("*.json*")):
        sample.write_text(
            json.dumps(
                [
                    {
                        "source": "forum",
                        "review_id": "forum-sample-1",
                        "title": "Zepto category exploration",
                        "body": (
                            "Has anyone else noticed it's hard to try new Zepto categories "
                            "when staples keep getting recommended first?"
                        ),
                        "posted_at": "2026-07-01T10:00:00+00:00",
                        "rating": 3,
                        "locale": "community-forum",
                    },
                    {
                        "source": "social",
                        "review_id": "social-sample-1",
                        "body": (
                            "Zepto 10-minute delivery was great tonight but refund chat "
                            "still needs work — quick commerce tradeoff."
                        ),
                        "posted_at": "2026-07-05T18:30:00+00:00",
                        "rating": 4,
                        "locale": "twitter-x",
                    },
                    {
                        "source": "quick_commerce",
                        "review_id": "qc-sample-1",
                        "body": (
                            "Comparing Blinkit vs Zepto for late night pharmacy — Zepto "
                            "had stock but ETA slipped past the promise."
                        ),
                        "posted_at": "2026-07-08T22:15:00+00:00",
                        "rating": 2,
                        "locale": "qc-thread",
                    },
                    {
                        "source": "product_review",
                        "review_id": "pr-sample-1",
                        "body": (
                            "Detailed Zepto app review: search is improving, but discovery "
                            "of new categories still depends heavily on deals and banners."
                        ),
                        "posted_at": "2026-07-10T09:00:00+00:00",
                        "rating": 4,
                        "locale": "blog-review",
                    },
                    {
                        "source": "reddit",
                        "review_id": "reddit-drop-1",
                        "title": "r/bangalore: Zepto habit vs exploring new categories",
                        "body": (
                            "I reorder milk and veggies from Zepto every other day out of habit, "
                            "but I rarely try cafe or pharmacy because I’m not sure about quality "
                            "from store reviews and delayed refunds scare me."
                        ),
                        "posted_at": "2026-07-06T14:00:00+00:00",
                        "rating": 3,
                        "locale": "r/bangalore",
                    },
                    {
                        "source": "reddit",
                        "review_id": "reddit-drop-2",
                        "title": "r/india: Zepto vs Blinkit discovery",
                        "body": (
                            "Blinkit banners push new categories harder. On Zepto I mostly see "
                            "the same staples unless there is a flash deal — discovery feels weaker."
                        ),
                        "posted_at": "2026-07-07T11:20:00+00:00",
                        "rating": 2,
                        "locale": "r/india",
                    },
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return root
