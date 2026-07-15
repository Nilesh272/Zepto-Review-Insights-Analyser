"""scrub_pii tool: NormalizedReview[] -> CleanReview[]; E2.8 no-leak property."""

import re
from datetime import datetime, timezone

from pulse.agent.budget import Budget
from pulse.agent.registry import RunContext
from pulse.agent.tools import build_default_registry
from pulse.config import Settings
from pulse.models import NormalizedReview
from pulse.preprocess.pii import Scrubber
from pulse.utils.text import text_fingerprint

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _norm(rid: str, body: str, author=None, title=None, lang="en") -> NormalizedReview:
    return NormalizedReview(
        source="app_store",
        product_id="groww",
        review_id=rid,
        rating=5,
        title=title,
        body=body,
        author=author,
        locale="in",
        posted_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
        text_fingerprint=text_fingerprint(body),
        word_count=len(body.split()),
        lang=lang,
    )


def _ctx(reviews) -> RunContext:
    ctx = RunContext(
        product_id="groww",
        iso_week="2026-W26",
        settings=Settings(),
        budget=Budget(max_tokens=1000, max_cost_usd=1.0),
    )
    ctx.bag["reviews"] = reviews
    return ctx


def test_tool_produces_clean_reviews():
    reviews = [
        _norm("1", "Contact me at jane@example.com about the slow login", author="Jane Roy"),
        _norm("2", "The new dashboard layout is clean and easy to navigate"),
    ]
    ctx = _ctx(reviews)
    out = build_default_registry().dispatch("scrub_pii", ctx)["result"]

    assert out["clean_reviews"] == 2
    assert out["reviews_with_pii"] == 1
    assert out["redactions"].get("EMAIL") == 1

    clean = ctx.bag["clean_reviews"]
    assert clean[0].body_clean.count("[EMAIL]") == 1
    assert not EMAIL_RE.search(clean[0].body_clean)
    assert clean[0].pii_spans  # audit recorded
    assert clean[0].lang == "en"  # carried from NormalizedReview


def test_title_is_scrubbed():
    reviews = [_norm("1", "Good app overall", title="ping me at sam@corp.com", author=None)]
    ctx = _ctx(reviews)
    build_default_registry().dispatch("scrub_pii", ctx)
    clean = ctx.bag["clean_reviews"][0]
    assert "[EMAIL]" in clean.title
    assert not EMAIL_RE.search(clean.title)


def test_no_pii_leaks_across_corpus():
    # E2.8 — a synthetic PII corpus must show zero leaks in body_clean.
    corpus = [
        "email me at a.b+test@mail.co.uk now",
        "call +91 90000 11111 urgently please",
        "card 4242 4242 4242 4242 got blocked",
        "account number 98765432100 is frozen",
        "reach support (at) helpdesk dot com for refunds",
    ]
    scrubber = Scrubber(redact_names=True)
    for text in corpus:
        cleaned = scrubber.scrub(text).body_clean
        assert not scrubber.has_pii(cleaned), f"leak in: {cleaned}"
        assert not EMAIL_RE.search(cleaned)
