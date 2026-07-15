"""render_report tool wiring + end-to-end summarize -> validate -> render."""

from pulse.agent.budget import Budget
from pulse.agent.registry import RunContext
from pulse.agent.tools import build_default_registry
from pulse.config import Settings
from pulse.models import Quote, RenderedReport, Theme
from pulse.render.docs import validate_docs_requests
from tests.synth import build_gold_clusters, build_themed_reviews


def _ctx(**bag):
    ctx = RunContext(
        product_id="groww", iso_week="2026-W26", settings=Settings(),
        budget=Budget(max_tokens=10**7, max_cost_usd=100.0),
    )
    ctx.bag.update(bag)
    return ctx


def test_render_tool_populates_bag_and_validates():
    themes = [
        Theme(title="Perf", summary="crashes", quotes=[Quote(text="it crashes a lot", review_id="r1", validated=True)],
              actions=["fix"], who_this_helps=["Product"]),
    ]
    ctx = _ctx(themes=themes, low_signal=False)
    out = build_default_registry().dispatch("render_report", ctx)["result"]

    assert out["section_anchor"] == "pulse-groww-2026-W26"
    assert out["themes_rendered"] == 1 and out["docs_requests"] > 0
    assert out["deep_link_filled"] is False  # filled in Phase 6

    report = ctx.bag["rendered"]
    assert isinstance(report, RenderedReport)
    validate_docs_requests(report.docs_requests)
    assert ctx.bag["section_anchor"] == "pulse-groww-2026-W26"


def test_render_tool_low_signal_when_no_themes():
    ctx = _ctx(themes=[], low_signal=True)
    out = build_default_registry().dispatch("render_report", ctx)["result"]
    assert out["low_signal"] is True and out["themes_rendered"] == 0
    text = "".join(r["insertText"]["text"] for r in ctx.bag["rendered"].docs_requests if "insertText" in r)
    assert "Low-signal" in text


def test_end_to_end_summarize_validate_render():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    reg = build_default_registry()
    ctx = _ctx(clean_reviews=reviews, clusters=clusters)

    reg.dispatch("summarize_clusters", ctx)
    reg.dispatch("validate_quotes", ctx)
    out = reg.dispatch("render_report", ctx)["result"]

    assert out["themes_rendered"] >= 1
    report = ctx.bag["rendered"]
    validate_docs_requests(report.docs_requests)
    # Every rendered quote is one of the validated quotes (verbatim).
    doc_text = "".join(r["insertText"]["text"] for r in report.docs_requests if "insertText" in r)
    for theme in ctx.bag["themes"]:
        for q in theme.quotes[: ctx.settings.render.max_quotes_per_theme]:
            assert q.text in doc_text
