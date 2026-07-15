"""Agent tools (architecture §3.2 skill tools, §3.3 MCP tools).

Implemented per phase:

  fetch_reviews        -> Phase 1 (ingestion)            [IMPLEMENTED]
  scrub_pii            -> Phase 2 (preprocessing & safety)   [stub]
  cluster_reviews      -> Phase 3 (embeddings + UMAP + HDBSCAN) [stub]
  summarize_clusters   -> Phase 4 (LLM themes/quotes/actions)  [stub]
  validate_quotes      -> Phase 4 (grounding hard gate)        [stub]
  render_report        -> Phase 5 (Docs requests + email)      [stub]
  docs_append_section  -> Phase 6 (Google Docs MCP)            [stub]
  gmail_draft_or_send  -> Phase 6 (Gmail MCP)                  [stub]
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
    # Imported lazily so optional deps (langdetect / google-play-scraper) load only when used.
    from pulse.ingestion.cache import RawCache
    from pulse.ingestion.service import run_ingestion
    from pulse.utils.isoweek import parse_iso_week

    if ctx.product is None:
        raise ValueError("fetch_reviews requires ctx.product to be set")

    iso = parse_iso_week(ctx.iso_week)
    cache = RawCache(ctx.cache_dir)
    result = run_ingestion(
        ctx.product,
        ctx.settings,
        iso,
        cache=cache,
        offline=ctx.offline,
    )

    ctx.bag["reviews"] = result.reviews
    ctx.bag["ingestion_stats"] = result.stats.model_dump()
    return {
        "kept": result.stats.kept,
        "input_total": result.stats.input_total,
        "source_counts": result.source_counts,
        "source_errors": result.source_errors,
        "dropped": {
            "duplicates_exact": result.stats.duplicates_exact,
            "duplicates_near": result.stats.duplicates_near,
            "out_of_window": result.stats.out_of_window,
            "quality": result.stats.dropped_quality,
        },
        "window": [result.window_start, result.window_end],
    }


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
