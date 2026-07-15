"""Agent core — planner + tool dispatcher (architecture §3.1, §4).

The core expands a run goal ``(product, iso_week)`` into an ordered plan, dispatches each tool
through the registry, enforces the per-run budget, and records the outcome in the run ledger.
Idempotency is enforced up front via the ledger short-circuit (architecture §8.3).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from pulse.agent.budget import Budget, BudgetExceededError
from pulse.agent.registry import RunContext, ToolRegistry
from pulse.agent.tools import DEFAULT_PLAN, build_default_registry
from pulse.config import Config
from pulse.state.ledger import RunLedger, utcnow
from pulse.utils.isoweek import parse_iso_week

logger = logging.getLogger("pulse.agent.core")


class RunSummary(BaseModel):
    product_id: str
    iso_week: str
    status: str  # COMPLETED | SKIPPED_ALREADY_COMPLETED | FAILED
    run_id: str
    dry_run: bool
    steps: list[str] = Field(default_factory=list)
    budget: dict = Field(default_factory=dict)
    section_anchor: str | None = None
    deep_link: str | None = None
    email_status: str | None = None
    metrics: dict = Field(default_factory=dict)
    error: str | None = None


def _build_metrics(ctx, results: dict, budget, *, started_at, finished_at, dry_run: bool) -> dict:
    """Assemble observability metrics for a run (architecture §12, eval E7.11).

    Pulls counts from the per-tool results / context bag; missing stages contribute zeros so the
    shape is stable even for partial (failed/halted) runs.
    """
    fetch = results.get("fetch_reviews", {})
    cluster = results.get("cluster_reviews", {})
    summarize = results.get("summarize_clusters", {})
    validate = results.get("validate_quotes", {})
    bsnap = budget.snapshot()
    return {
        "reviews_in": fetch.get("kept", 0),
        "clusters": cluster.get("clusters", 0),
        "themes": validate.get("themes", summarize.get("themes", 0)),
        "quotes_validated": validate.get("validated_quotes", 0),
        "quotes_dropped": validate.get("dropped_quotes", 0),
        "budget_halted": summarize.get("budget_halted", False),
        "low_signal": ctx.bag.get("low_signal", False),
        "tokens": bsnap["tokens"],
        "cost_usd": bsnap["cost_usd"],
        "latency_seconds": round((finished_at - started_at).total_seconds(), 3),
        "dry_run": dry_run,
    }


class AgentCore:
    def __init__(self, config: Config, ledger: RunLedger, registry: ToolRegistry | None = None):
        self.config = config
        self.ledger = ledger
        self.registry = registry or build_default_registry()

    def plan(self, product_id: str, iso_week: str) -> list[str]:
        """Expand the run goal into an ordered list of tool calls."""
        return list(DEFAULT_PLAN)

    def run(
        self,
        product_id: str,
        iso_week: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        offline: bool = False,
        cache_dir: str = ".pulse/cache",
    ) -> RunSummary:
        # Validate inputs up front (fail fast — X0.1/X0.2/X0.3).
        parse_iso_week(iso_week)
        product = self.config.registry.get(product_id)  # raises KeyError if unknown

        # Capture any prior delivery state for reconciliation (X6.7 / E6.7) before reclaiming.
        prior = self.ledger.get(product.id, iso_week)

        record, already_completed = self.ledger.try_start(
            product.id,
            iso_week,
            force=force,
            stale_after_minutes=self.config.settings.stale_run_minutes,
        )

        if already_completed:
            logger.info("run %s %s already COMPLETED — no-op", product.id, iso_week)
            return RunSummary(
                product_id=product.id,
                iso_week=iso_week,
                status="SKIPPED_ALREADY_COMPLETED",
                run_id=record.run_id,
                dry_run=dry_run,
                steps=[],
                budget={},
                section_anchor=record.section_anchor,
            )

        budget = Budget(
            max_tokens=self.config.settings.limits.max_tokens_per_run,
            max_cost_usd=self.config.settings.limits.max_cost_usd_per_run,
        )
        ctx = RunContext(
            product_id=product.id,
            iso_week=iso_week,
            settings=self.config.settings,
            budget=budget,
            dry_run=dry_run,
            force=force,
            product=product,
            offline=offline,
            cache_dir=cache_dir,
        )
        if prior is not None:
            ctx.bag["prior_delivery"] = {
                "email_status": prior.email_status,
                "message_id": prior.message_id,
                "doc_id": prior.doc_id,
                "heading_id": prior.heading_id,
                "deep_link": prior.deep_link,
                "section_anchor": prior.section_anchor,
            }

        started_at = record.started_at
        executed: list[str] = []
        results: dict = {}
        try:
            for step in self.plan(product.id, iso_week):
                out = self.registry.dispatch(step, ctx)
                results[step] = out.get("result", {})
                executed.append(step)
        except BudgetExceededError as exc:
            return self._fail(record, ctx, executed, budget, results, str(exc))
        except Exception as exc:  # noqa: BLE001 - record any tool failure as FAILED, re-runnable
            return self._fail(record, ctx, executed, budget, results, repr(exc))

        finished_at = datetime.now(timezone.utc)
        record.status = "COMPLETED"
        record.finished_at = finished_at
        record.section_anchor = ctx.bag.get("section_anchor")
        # Record delivery identifiers for audit (E6.9). Preserve prior ids on dry-run/skip.
        record.doc_id = ctx.bag.get("doc_id") or (prior.doc_id if prior else None)
        record.heading_id = ctx.bag.get("heading_id") or (prior.heading_id if prior else None)
        record.deep_link = ctx.bag.get("deep_link") or (prior.deep_link if prior else None)
        record.email_status = ctx.bag.get("email_status") or (prior.email_status if prior else "none")
        record.message_id = ctx.bag.get("message_id") or (prior.message_id if prior else None)
        metrics = _build_metrics(
            ctx, results, budget, started_at=started_at, finished_at=finished_at, dry_run=dry_run
        )
        record.metrics = {"steps": executed, **metrics}
        self.ledger.upsert(record)
        if not dry_run:
            try:
                from pulse.render.dashboard import upsert_run

                upsert_run(
                    self.config.settings.mcp.local_output_dir,
                    product_id=product.id,
                    product_name=product.name,
                    doc_id=product.doc_id,
                    iso_week=iso_week,
                    fetch=results.get("fetch_reviews", {}),
                    metrics=metrics,
                    section_anchor=record.section_anchor,
                )
            except Exception:  # noqa: BLE001 — dashboard must never fail the run
                logger.exception("dashboard update failed for %s %s", product.id, iso_week)
        logger.info(
            "run %s %s COMPLETED (%d reviews, %d themes, %.3fs)",
            product.id, iso_week, metrics["reviews_in"], metrics["themes"], metrics["latency_seconds"],
        )

        return RunSummary(
            product_id=product.id,
            iso_week=iso_week,
            status="COMPLETED",
            run_id=record.run_id,
            dry_run=dry_run,
            steps=executed,
            budget=budget.snapshot(),
            section_anchor=record.section_anchor,
            deep_link=record.deep_link,
            email_status=record.email_status,
            metrics=metrics,
        )

    def _fail(self, record, ctx, executed, budget, results, error: str) -> RunSummary:
        finished_at = utcnow()
        record.status = "FAILED"
        record.finished_at = finished_at
        record.error = error
        # Record partial metrics so a failed/halted run is still observable (X7.8 / X7.13).
        metrics = _build_metrics(
            ctx, results, budget, started_at=record.started_at, finished_at=finished_at,
            dry_run=ctx.dry_run,
        )
        record.metrics = {"steps": executed, **metrics}
        record.section_anchor = ctx.bag.get("section_anchor") or record.section_anchor
        record.doc_id = ctx.bag.get("doc_id") or record.doc_id
        record.heading_id = ctx.bag.get("heading_id") or record.heading_id
        record.deep_link = ctx.bag.get("deep_link") or record.deep_link
        record.email_status = ctx.bag.get("email_status") or record.email_status
        record.message_id = ctx.bag.get("message_id") or record.message_id
        self.ledger.upsert(record)
        logger.warning("run %s %s FAILED: %s", record.product_id, record.iso_week, error)
        return RunSummary(
            product_id=record.product_id,
            iso_week=record.iso_week,
            status="FAILED",
            run_id=record.run_id,
            dry_run=ctx.dry_run,
            steps=executed,
            budget=budget.snapshot(),
            section_anchor=record.section_anchor,
            deep_link=record.deep_link,
            email_status=record.email_status,
            metrics=metrics,
            error=error,
        )
