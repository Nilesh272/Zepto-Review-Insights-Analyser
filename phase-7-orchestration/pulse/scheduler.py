"""Weekly scheduling (architecture §9, §4).

Runs the agent once per configured product for the **just-completed ISO week**, isolating
failures so one product's failure never blocks the others (E7.4 / X7.1). The trigger week is
computed in **IST** (the cadence is "Monday morning IST"), while all internal times stay UTC;
ISO-calendar arithmetic handles the year boundary (W52/W53 → W01, X7.6) and there is no DST in
India so the fixed offset is exact (X7.5).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from pulse.agent.core import AgentCore, RunSummary
from pulse.config import Config
from pulse.state.ledger import RunLedger
from pulse.utils.isoweek import IsoWeek

logger = logging.getLogger("pulse.scheduler")

IST = timezone(timedelta(hours=5, minutes=30))


def just_completed_iso_week(now: datetime | None = None) -> IsoWeek:
    """The ISO week that has just finished, as seen from IST 'now' (defaults to current time)."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    ist = now.astimezone(IST)
    y, w, _ = ist.isocalendar()
    # Step back one day from this week's Monday to land on the previous (completed) week.
    monday = date.fromisocalendar(y, w, 1)
    prev = (monday - timedelta(days=1)).isocalendar()
    return IsoWeek(year=prev[0], week=prev[1])


def run_weekly(
    config: Config,
    ledger: RunLedger,
    *,
    now: datetime | None = None,
    iso_week: str | None = None,
    product_ids: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
    offline: bool = False,
    cache_dir: str = ".pulse/cache",
) -> list[RunSummary]:
    """Run every configured product for the target week; failures are isolated per product."""
    week = iso_week or str(just_completed_iso_week(now))
    ids = product_ids or config.registry.ids()
    agent = AgentCore(config=config, ledger=ledger)

    summaries: list[RunSummary] = []
    for pid in ids:
        try:
            summary = agent.run(
                pid, week, dry_run=dry_run, force=force, offline=offline, cache_dir=cache_dir
            )
        except Exception as exc:  # noqa: BLE001 - isolate per-product failures (E7.4 / X7.1)
            logger.warning("scheduled run for %s %s raised: %r", pid, week, exc)
            summary = RunSummary(
                product_id=pid, iso_week=week, status="FAILED", run_id="",
                dry_run=dry_run, error=repr(exc),
            )
        summaries.append(summary)

    completed = sum(1 for s in summaries if s.status in {"COMPLETED", "SKIPPED_ALREADY_COMPLETED"})
    logger.info("weekly run %s: %d/%d products ok", week, completed, len(summaries))
    return summaries
