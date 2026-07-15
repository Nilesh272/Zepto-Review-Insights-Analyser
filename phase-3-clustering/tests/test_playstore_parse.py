"""E1.2 — Google Play raw-dict parsing to RawReview."""

from datetime import timezone

from pulse.ingestion.playstore import parse_play_entries


def test_parse_play_entries(play_entries):
    reviews = parse_play_entries(play_entries, "groww")
    assert len(reviews) == 3
    assert all(r.source == "play_store" for r in reviews)
    p1 = reviews[0]
    assert p1.review_id == "p1"
    assert p1.rating == 5
    assert p1.author == "Divya"
    assert p1.app_version == "5.2.1"
    assert p1.posted_at.tzinfo == timezone.utc


def test_skips_entries_without_score():
    entries = [{"reviewId": "x", "content": "no score here at all", "at": "2026-06-26T00:00:00+00:00"}]
    assert parse_play_entries(entries, "groww") == []
