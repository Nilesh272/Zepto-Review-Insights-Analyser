"""E4.1/E4.2 end-to-end through the agent registry: summarize -> validate, fully grounded."""

from pulse.agent.budget import Budget
from pulse.agent.registry import RunContext
from pulse.agent.tools import build_default_registry
from pulse.config import Settings
from tests.synth import build_gold_clusters, build_themed_reviews


def _ctx(reviews, clusters):
    ctx = RunContext(
        product_id="groww", iso_week="2026-W26", settings=Settings(),
        budget=Budget(max_tokens=10**7, max_cost_usd=100.0),
    )
    ctx.bag["clean_reviews"] = reviews
    ctx.bag["clusters"] = clusters
    return ctx


def test_pipeline_summarize_then_validate_is_grounded():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    reg = build_default_registry()
    ctx = _ctx(reviews, clusters)

    s = reg.dispatch("summarize_clusters", ctx)["result"]
    assert s["themes"] == 3 and not s["low_signal"]

    v = reg.dispatch("validate_quotes", ctx)["result"]
    assert v["validated_quotes"] > 0
    assert v["dropped_quotes"] == 0  # extractive candidates are all grounded

    # E4.1/E4.2: every published quote is verbatim in its cited review.
    bodies = {r.review_id: r.body_clean for r in reviews}
    for theme in ctx.bag["themes"]:
        for q in theme.quotes:
            assert q.validated is True
            assert q.text in bodies[q.review_id]


def test_pipeline_low_signal_no_clusters():
    reviews, _ = build_themed_reviews(repeats=3)
    reg = build_default_registry()
    ctx = _ctx(reviews, [])
    s = reg.dispatch("summarize_clusters", ctx)["result"]
    assert s["low_signal"] is True and s["themes"] == 0
    v = reg.dispatch("validate_quotes", ctx)["result"]
    assert v["themes"] == 0
