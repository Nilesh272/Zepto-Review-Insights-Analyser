"""Phase 0 stub tools (architecture §3.2 skill tools, §3.3 MCP tools).

These are placeholders that exercise the agent loop, budget, and registry without doing real
work. Later phases replace each stub with its real implementation:

  fetch_reviews        -> Phase 1 (ingestion)
  scrub_pii            -> Phase 2 (preprocessing & safety)
  cluster_reviews      -> Phase 3 (embeddings + UMAP + HDBSCAN)
  summarize_clusters   -> Phase 4 (LLM themes/quotes/actions)
  validate_quotes      -> Phase 4 (grounding hard gate)
  render_report        -> Phase 5 (Docs requests + email)
  docs_append_section  -> Phase 6 (Google Docs MCP)
  gmail_draft_or_send  -> Phase 6 (Gmail MCP)
"""

from __future__ import annotations

from pulse.agent.registry import RunContext, ToolRegistry

# Ordered plan the agent core executes (architecture §4).
DEFAULT_PLAN = [
    "fetch_reviews",
    "scrub_pii",
    "cluster_reviews",
    "summarize_clusters",
    "validate_quotes",
    "render_report",
    "docs_append_section",
    "gmail_draft_or_send",
]


def _fetch_reviews(ctx: RunContext) -> dict:
    ctx.bag["reviews"] = []
    return {"stub": True, "reviews": 0, "window_weeks": ctx.settings.window_weeks}


def _scrub_pii(ctx: RunContext) -> dict:
    ctx.bag["clean_reviews"] = []
    return {"stub": True, "scrubbed": 0}


def _cluster_reviews(ctx: RunContext) -> dict:
    ctx.bag["clusters"] = []
    return {"stub": True, "clusters": 0}


def _summarize_clusters(ctx: RunContext) -> dict:
    # Simulate a small LLM cost so budget enforcement is exercised end-to-end.
    ctx.budget.add(tokens=10, cost_usd=0.0001)
    ctx.bag["themes"] = []
    return {"stub": True, "themes": 0}


def _validate_quotes(ctx: RunContext) -> dict:
    return {"stub": True, "validated_quotes": 0, "dropped_quotes": 0}


def _render_report(ctx: RunContext) -> dict:
    # Deterministic anchor per architecture §8.1: pulse-<product>-<iso_week> (e.g. ...-2026-W26)
    anchor = f"pulse-{ctx.product_id}-{ctx.iso_week}"
    ctx.bag["section_anchor"] = anchor
    return {"stub": True, "section_anchor": anchor}


def _docs_append_section(ctx: RunContext) -> dict:
    return {"stub": True, "appended": False}


def _gmail_draft_or_send(ctx: RunContext) -> dict:
    return {"stub": True, "email_status": "none", "mode": ctx.settings.email_mode}


def build_default_registry() -> ToolRegistry:
    """Register the Phase 0 stub tools (6 skill tools + 2 MCP tools)."""
    reg = ToolRegistry()
    reg.register("fetch_reviews", _fetch_reviews, kind="skill", description="Ingest reviews")
    reg.register("scrub_pii", _scrub_pii, kind="skill", description="PII scrub + language")
    reg.register("cluster_reviews", _cluster_reviews, kind="skill", description="Cluster")
    reg.register("summarize_clusters", _summarize_clusters, kind="skill", description="LLM")
    reg.register("validate_quotes", _validate_quotes, kind="skill", description="Grounding")
    reg.register("render_report", _render_report, kind="skill", description="Render")
    reg.register("docs_append_section", _docs_append_section, kind="mcp", description="Docs MCP")
    reg.register("gmail_draft_or_send", _gmail_draft_or_send, kind="mcp", description="Gmail MCP")
    return reg
