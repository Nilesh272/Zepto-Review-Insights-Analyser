"""E1.4/E1.8 service merge + determinism; X1.2 per-source error isolation."""

import json

from pulse.config import Product, Settings
from pulse.ingestion.service import run_ingestion
from pulse.utils.isoweek import parse_iso_week

PRODUCT = Product(
    id="groww", name="Groww", app_store_id="123", play_package="com.groww", doc_id="D"
)
WEEK = parse_iso_week("2026-W26")


def _http_get(appstore_page1, appstore_empty):
    def get(url: str) -> str:
        return json.dumps(appstore_page1 if "page=1/" in url else appstore_empty)

    return get


def _play_fetcher(play_entries):
    def fetch(package, lang, country, count):
        return play_entries

    return fetch


def test_service_merges_both_sources(appstore_page1, appstore_empty, play_entries, fake_detector, no_sleep):
    result = run_ingestion(
        PRODUCT,
        Settings(),
        WEEK,
        detector=fake_detector,
        appstore_http_get=_http_get(appstore_page1, appstore_empty),
        play_fetcher=_play_fetcher(play_entries),
        sleep=no_sleep,
    )
    assert result.source_counts == {"app_store": 6, "play_store": 3}
    assert result.source_errors == {}
    assert result.stats.kept == 3


def test_service_is_deterministic(appstore_page1, appstore_empty, play_entries, fake_detector, no_sleep):
    kwargs = dict(
        detector=fake_detector,
        appstore_http_get=_http_get(appstore_page1, appstore_empty),
        play_fetcher=_play_fetcher(play_entries),
        sleep=no_sleep,
    )
    r1 = run_ingestion(PRODUCT, Settings(), WEEK, **kwargs)
    r2 = run_ingestion(PRODUCT, Settings(), WEEK, **kwargs)
    assert [r.review_id for r in r1.reviews] == [r.review_id for r in r2.reviews]


def test_source_failure_is_isolated(play_entries, fake_detector, no_sleep):
    def boom(url: str) -> str:
        raise RuntimeError("network down")

    result = run_ingestion(
        PRODUCT,
        Settings(),
        WEEK,
        detector=fake_detector,
        appstore_http_get=boom,
        play_fetcher=_play_fetcher(play_entries),
        sleep=no_sleep,
    )
    assert "app_store" in result.source_errors
    assert result.source_counts.get("play_store") == 3
    # All three Play reviews survive (the near-dup's App Store twin is absent).
    assert result.stats.kept == 3
