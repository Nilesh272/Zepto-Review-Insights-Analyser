"""Shared builders for Phase 6 delivery tests."""

from __future__ import annotations

from pulse.agent.budget import Budget
from pulse.agent.registry import RunContext
from pulse.config import Product, Settings
from pulse.models import Quote, RenderedReport, Theme
from pulse.render.docs import build_docs_requests, section_anchor
from pulse.render.email import render_email


def make_report(product_id="groww", iso_week="2026-W26", low_signal=False) -> RenderedReport:
    cfg = Settings().render
    themes = (
        []
        if low_signal
        else [
            Theme(
                title="App performance & bugs",
                summary="Crashes during trading hours.",
                quotes=[Quote(text="the app freezes at market open", review_id="r1", validated=True)],
                actions=["Stabilize peak-time performance"],
                who_this_helps=["Product", "Leadership"],
            )
        ]
    )
    anchor = section_anchor(product_id, iso_week)
    docs_requests = build_docs_requests(
        themes, product_name="Groww", iso_week=iso_week, anchor=anchor, cfg=cfg, low_signal=low_signal
    )
    email = render_email(themes, product_name="Groww", iso_week=iso_week, cfg=cfg, low_signal=low_signal)
    return RenderedReport(
        product_id=product_id, iso_week=iso_week, section_anchor=anchor,
        docs_requests=docs_requests, email=email, low_signal=low_signal,
    )


def make_ctx(
    *,
    settings: Settings | None = None,
    docs_mcp=None,
    gmail_mcp=None,
    force=False,
    recipients=("product-pulse@example.com",),
    doc_id="doc-groww",
    prior_delivery=None,
) -> RunContext:
    product = Product(
        id="groww", name="Groww", app_store_id="1", play_package="com.groww",
        doc_id=doc_id, recipients=list(recipients),
    )
    ctx = RunContext(
        product_id="groww", iso_week="2026-W26", settings=settings or Settings(),
        budget=Budget(max_tokens=10**7, max_cost_usd=100.0),
        force=force, product=product, docs_mcp=docs_mcp, gmail_mcp=gmail_mcp,
    )
    if prior_delivery is not None:
        ctx.bag["prior_delivery"] = prior_delivery
    return ctx
