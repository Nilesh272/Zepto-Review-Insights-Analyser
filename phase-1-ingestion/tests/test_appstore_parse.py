"""E1.1 — App Store RSS JSON parsing; app-metadata entry skipped; UTC timestamps."""

from datetime import timezone

from pulse.ingestion.appstore import build_feed_url, parse_app_store_json


def test_parse_skips_app_metadata(appstore_page1):
    reviews = parse_app_store_json(appstore_page1, "groww")
    # 6 review entries (the app-metadata entry has no im:rating and is skipped).
    assert len(reviews) == 6
    assert all(r.source == "app_store" for r in reviews)


def test_fields_mapped(appstore_page1):
    reviews = parse_app_store_json(appstore_page1, "groww")
    first = reviews[0]
    assert first.review_id == "1001"
    assert first.rating == 5
    assert first.author == "Asha"
    assert first.app_version == "5.2.1"
    assert first.body.startswith("This app makes tracking")
    assert first.posted_at.tzinfo == timezone.utc


def test_ratings_in_range(appstore_page1):
    reviews = parse_app_store_json(appstore_page1, "groww")
    assert all(1 <= r.rating <= 5 for r in reviews)


def test_parse_accepts_raw_string():
    payload = '{"feed": {"entry": {"im:name": {"label": "X"}}}}'
    assert parse_app_store_json(payload, "groww") == []


def test_build_feed_url():
    url = build_feed_url("123", "IN", 2)
    assert "id=123" in url and "page=2" in url and "/in/" in url
