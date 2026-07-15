"""E1.5-E1.8 — dedup (exact + near), window filter, and full normalize pipeline stats."""

from datetime import datetime, timedelta, timezone

from pulse.config import Settings
from pulse.ingestion.appstore import parse_app_store_json
from pulse.ingestion.normalize import normalize_reviews
from pulse.ingestion.playstore import parse_play_entries
from pulse.ingestion.service import compute_window
from pulse.utils.isoweek import parse_iso_week


def _window():
    return compute_window(parse_iso_week("2026-W26"), 12)


def test_full_pipeline_stats(appstore_page1, play_entries, fake_detector):
    raw = parse_app_store_json(appstore_page1, "groww") + parse_play_entries(play_entries, "groww")
    start, end = _window()
    result = normalize_reviews(
        raw, settings=Settings(), window_start=start, window_end=end, detector=fake_detector
    )
    s = result.stats
    assert s.input_total == 9
    assert s.duplicates_exact == 1       # id 1001 appears twice in the App Store feed
    assert s.duplicates_near == 1        # play p2 duplicates App Store 1001 body
    assert s.out_of_window == 1          # id 1005 dated 2026-01-01
    assert s.dropped_quality == {"emoji": 1, "too_short": 1, "language:fr": 1}
    assert s.kept == 3


def test_kept_reviews_are_english_and_sorted(appstore_page1, play_entries, fake_detector):
    raw = parse_app_store_json(appstore_page1, "groww") + parse_play_entries(play_entries, "groww")
    start, end = _window()
    kept = normalize_reviews(
        raw, settings=Settings(), window_start=start, window_end=end, detector=fake_detector
    ).reviews
    assert [r.review_id for r in kept] == ["p3", "p1", "1001"]  # newest first
    assert all(r.lang == "en" for r in kept)
    assert all(r.text_fingerprint for r in kept)


def test_window_boundaries_inclusive(fake_detector):
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 28, 23, 59, 59, tzinfo=timezone.utc)
    from pulse.models import RawReview

    def mk(rid, when):
        return RawReview(
            source="app_store", product_id="groww", review_id=rid, rating=5,
            body=f"a genuinely useful review number {rid} about investing",
            locale="in", posted_at=when,
        )

    raw = [
        mk("on_start", start),
        mk("on_end", end),
        mk("before", start - timedelta(seconds=1)),
        mk("after", end + timedelta(seconds=1)),
    ]
    kept_ids = {
        r.review_id
        for r in normalize_reviews(
            raw, settings=Settings(), window_start=start, window_end=end, detector=fake_detector
        ).reviews
    }
    assert kept_ids == {"on_start", "on_end"}
