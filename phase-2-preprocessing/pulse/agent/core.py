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
    error: str | None = None


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
            product=product,
            offline=offline,
            cache_dir=cache_dir,
        )

        executed: list[str] = []
        try:
            for step in self.plan(product.id, iso_week):
                self.registry.dispatch(step, ctx)
                executed.append(step)
        except BudgetExceededError as exc:
            return self._fail(record, ctx, executed, budget, str(exc))
        except Exception as exc:  # noqa: BLE001 - record any tool failure as FAILED, re-runnable
            return self._fail(record, ctx, executed, budget, repr(exc))

        record.status = "COMPLETED"
        record.finished_at = datetime.now(timezone.utc)
        record.section_anchor = ctx.bag.get("section_anchor")
        record.metrics = {
            "steps": executed,
            "dry_run": dry_run,
            "budget": budget.snapshot(),
        }
        self.ledger.upsert(record)
        logger.info("run %s %s COMPLETED", product.id, iso_week)

        return RunSummary(
            product_id=product.id,
            iso_week=iso_week,
            status="COMPLETED",
            run_id=record.run_id,
            dry_run=dry_run,
            steps=executed,
            budget=budget.snapshot(),
            section_anchor=record.section_anchor,
        )

    def _fail(self, record, ctx, executed, budget, error: str) -> RunSummary:
        record.status = "FAILED"
        record.finished_at = utcnow()
        record.error = error
        record.metrics = {"steps": executed, "budget": budget.snapshot()}
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
            error=error,
        )
