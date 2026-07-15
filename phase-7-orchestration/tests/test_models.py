"""E0.1 — data contracts round-trip; boundary values validate/reject."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from pulse.models import CleanReview, Cluster, Quote, RawReview, RunRecord, Span, Theme


def _raw(**over) -> RawReview:
    base = dict(
        source="app_store",
        product_id="groww",
        review_id="r1",
        rating=5,
        body="great app",
        locale="en-IN",
        posted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    base.update(over)
    return RawReview(**base)


def test_raw_review_round_trip():
    r = _raw(title="nice", author="a", app_version="1.2.3")
    again = RawReview.model_validate_json(r.model_dump_json())
    assert again == r


def test_rating_bounds_enforced():
    with pytest.raises(ValidationError):
        _raw(rating=0)
    with pytest.raises(ValidationError):
        _raw(rating=6)


def test_clean_review_extends_raw():
    c = CleanReview(
        **_raw().model_dump(),
        body_clean="great app",
        lang="en",
        pii_spans=[Span(start=0, end=4, label="EMAIL")],
    )
    again = CleanReview.model_validate_json(c.model_dump_json())
    assert again == c
    assert again.pii_spans[0].label == "EMAIL"


def test_theme_quote_round_trip():
    t = Theme(
        title="App performance",
        summary="crashes",
        quotes=[Quote(text="it freezes", review_id="r1", validated=True)],
        actions=["stabilize"],
        who_this_helps=["Product"],
    )
    assert Theme.model_validate_json(t.model_dump_json()) == t


def test_cluster_round_trip():
    c = Cluster(cluster_id=1, review_ids=["r1", "r2"], size=2, score=1.5, avg_rating=4.0)
    assert Cluster.model_validate_json(c.model_dump_json()) == c


def test_run_record_round_trip():
    rec = RunRecord(
        run_id="abc",
        product_id="groww",
        iso_week="2026-W26",
        started_at=datetime(2026, 6, 29, tzinfo=timezone.utc),
        metrics={"steps": ["fetch_reviews"]},
    )
    assert RunRecord.model_validate_json(rec.model_dump_json()) == rec
