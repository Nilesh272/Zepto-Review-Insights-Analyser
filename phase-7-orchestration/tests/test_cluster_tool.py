"""cluster_reviews tool wired into the agent registry."""

from pulse.agent.budget import Budget
from pulse.agent.registry import RunContext
from pulse.agent.tools import build_default_registry
from pulse.config import Settings
from tests.synth import build_themed_reviews


def _ctx(reviews):
    ctx = RunContext(
        product_id="groww",
        iso_week="2026-W26",
        settings=Settings(
            reasoning={"clusterer": "fallback", "stratify_by_rating": False},
            summarize={"min_critical_themes": 0},
        ),
        budget=Budget(max_tokens=1000, max_cost_usd=1.0),
    )
    ctx.bag["clean_reviews"] = reviews
    return ctx


def test_tool_clusters_and_populates_bag():
    reviews, _ = build_themed_reviews(repeats=3)
    ctx = _ctx(reviews)
    out = build_default_registry().dispatch("cluster_reviews", ctx)["result"]

    assert out["input_reviews"] == len(reviews)
    assert out["clusters"] == 3
    assert ctx.bag["clusters"] and len(ctx.bag["clusters"]) == 3
    assert ctx.bag["top_clusters"] == ctx.bag["clusters"][:5]


def test_tool_low_signal_empty():
    reviews, _ = build_themed_reviews(repeats=3)
    ctx = _ctx(reviews[:3])
    out = build_default_registry().dispatch("cluster_reviews", ctx)["result"]
    assert out["clusters"] == 0
    assert ctx.bag["clusters"] == []
