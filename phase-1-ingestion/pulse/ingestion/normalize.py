"""Merge, dedup, window, and quality-filter raw reviews into NormalizedReview[] (architecture §3.2).

Pipeline order (deterministic):
  1. exact dedup     — by (source, review_id)
  2. near-dup dedup  — by normalized-text fingerprint
  3. window filter   — keep posted_at within [window_start, window_end]
  4. quality filters — emoji / too_short / other-language (per requested rules)
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from pydantic import BaseModel, Field

from pulse.config import Settings
from pulse.ingestion.filters import Detector, classify
from pulse.models import NormalizedReview, RawReview
from pulse.utils.text import text_fingerprint


class NormalizeStats(BaseModel):
    input_total: int = 0
    duplicates_exact: int = 0
    duplicates_near: int = 0
    out_of_window: int = 0
    dropped_quality: dict[str, int] = Field(default_factory=dict)
    kept: int = 0

    @property
    def dropped_total(self) -> int:
        return (
            self.duplicates_exact
            + self.duplicates_near
            + self.out_of_window
            + sum(self.dropped_quality.values())
        )


class NormalizeResult(BaseModel):
    reviews: list[NormalizedReview]
    stats: NormalizeStats


def normalize_reviews(
    raw: list[RawReview],
    *,
    settings: Settings,
    window_start: datetime,
    window_end: datetime,
    detector: Detector,
) -> NormalizeResult:
    stats = NormalizeStats(input_total=len(raw))
    quality_drops: Counter[str] = Counter()

    # 1. exact dedup by (source, review_id) — only when an id is present.
    seen_ids: set[tuple[str, str]] = set()
    after_exact: list[RawReview] = []
    for r in raw:
        if r.review_id:
            key = (r.source, r.review_id)
            if key in seen_ids:
                stats.duplicates_exact += 1
                continue
            seen_ids.add(key)
        after_exact.append(r)

    # 2. near-dup dedup by normalized-text fingerprint (keep first occurrence).
    seen_fp: set[str] = set()
    after_near: list[tuple[RawReview, str]] = []
    for r in after_exact:
        fp = text_fingerprint(r.body)
        if fp in seen_fp:
            stats.duplicates_near += 1
            continue
        seen_fp.add(fp)
        after_near.append((r, fp))

    # 3. window filter (inclusive on both ends).
    in_window: list[tuple[RawReview, str]] = []
    for r, fp in after_near:
        if window_start <= r.posted_at <= window_end:
            in_window.append((r, fp))
        else:
            stats.out_of_window += 1

    # 4. quality filters.
    kept: list[NormalizedReview] = []
    for r, fp in in_window:
        c = classify(r.body, settings, detector)
        if c.reason is not None:
            quality_drops[c.reason] += 1
            continue
        kept.append(
            NormalizedReview(
                **r.model_dump(),
                text_fingerprint=fp,
                word_count=c.word_count,
                lang=c.lang,
            )
        )

    # Stable, deterministic ordering: newest first, then review id.
    kept.sort(key=lambda x: (x.posted_at, x.review_id), reverse=True)

    stats.dropped_quality = dict(quality_drops)
    stats.kept = len(kept)
    return NormalizeResult(reviews=kept, stats=stats)
