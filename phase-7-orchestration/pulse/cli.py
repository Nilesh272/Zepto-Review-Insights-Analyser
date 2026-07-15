"""CLI entry point (architecture §9).

Subcommands:
  run       — full agent run for a product + ISO week (backfill any week via --week).
  ingest    — Phase 1 only: fetch + normalize + filter reviews and print ingestion stats.
  schedule  — run all configured products for the just-completed ISO week (weekly cadence).
  audit     — query the ledger: "what was sent when, for which week?".

Email send gating (E7.9 / X7.11): the EMAIL_MODE environment variable overrides config and is
**fail-safe** — anything other than an explicit ``send`` resolves to ``draft``.

Usage:
    python -m pulse.cli run --product groww --week 2026-W26 [--dry-run] [--offline] [--force]
    python -m pulse.cli schedule [--dry-run] [--offline] [--force]
    python -m pulse.cli audit --product groww --week 2026-W26
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from pulse.env import load_env

load_env()

from pulse.agent.core import AgentCore, RunSummary
from pulse.config import Config, load_config
from pulse.scheduler import just_completed_iso_week, run_weekly
from pulse.state.ledger import RunInProgressError, RunLedger
from pulse.utils.isoweek import IsoWeekError, current_iso_week, parse_iso_week

logger = logging.getLogger("pulse.cli")

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_DEFAULT_LEDGER = ".pulse/ledger.db"
_DEFAULT_CACHE = ".pulse/cache"


def resolve_email_mode(configured: str, env: dict | None = None) -> str:
    """Fail-safe send gating: only an explicit EMAIL_MODE=send enables sending (E7.9 / X7.11)."""
    env = env if env is not None else os.environ
    raw = env.get("EMAIL_MODE")
    if raw is None:
        return configured
    value = raw.strip().lower()
    if value == "send":
        return "send"
    if value != "draft":
        logger.warning("EMAIL_MODE=%r is not 'draft' or 'send' — defaulting to safe 'draft'", raw)
    return "draft"


def _apply_email_gating(config: Config) -> Config:
    config.settings.email_mode = resolve_email_mode(config.settings.email_mode)
    return config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pulse", description="Weekly Product Review Pulse agent")
    parser.add_argument("--config-dir", default=str(_DEFAULT_CONFIG_DIR), help="Config directory")
    parser.add_argument("--ledger", default=_DEFAULT_LEDGER, help="Path to the run ledger DB")
    parser.add_argument("--cache-dir", default=_DEFAULT_CACHE, help="Raw fetch cache directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the pulse for a product + ISO week")
    run_p.add_argument("--product", required=True, help="Product id (see config/products.yaml)")
    run_p.add_argument("--week", help="ISO week 'YYYY-Www' (defaults to current ISO week)")
    run_p.add_argument("--dry-run", action="store_true", help="Plan + run skills, skip MCP writes")
    run_p.add_argument("--force", action="store_true", help="Re-run even if already completed")
    run_p.add_argument("--offline", action="store_true", help="Use only cached raw fetches")

    ing_p = sub.add_parser("ingest", help="Fetch + normalize reviews and print stats (Phase 1)")
    ing_p.add_argument("--product", required=True, help="Product id (see config/products.yaml)")
    ing_p.add_argument("--week", help="ISO week 'YYYY-Www' (defaults to current ISO week)")
    ing_p.add_argument("--offline", action="store_true", help="Use only cached raw fetches")
    ing_p.add_argument("--show", type=int, default=0, help="Print up to N kept review bodies")

    sch_p = sub.add_parser("schedule", help="Run all products for the just-completed ISO week")
    sch_p.add_argument("--week", help="Override the target ISO week (defaults to just-completed)")
    sch_p.add_argument("--product", action="append", dest="products", help="Limit to product id(s)")
    sch_p.add_argument("--dry-run", action="store_true", help="Plan + run skills, skip MCP writes")
    sch_p.add_argument("--force", action="store_true", help="Re-run even if already completed")
    sch_p.add_argument("--offline", action="store_true", help="Use only cached raw fetches")

    aud_p = sub.add_parser("audit", help="Query the ledger for a product + ISO week")
    aud_p.add_argument("--product", required=True, help="Product id")
    aud_p.add_argument("--week", required=True, help="ISO week 'YYYY-Www'")
    return parser


def run_command(args: argparse.Namespace) -> RunSummary:
    config = _apply_email_gating(load_config(args.config_dir))
    iso_week = args.week or str(current_iso_week())
    with RunLedger(args.ledger) as ledger:
        agent = AgentCore(config=config, ledger=ledger)
        return agent.run(
            product_id=args.product,
            iso_week=iso_week,
            dry_run=args.dry_run,
            force=args.force,
            offline=args.offline,
            cache_dir=args.cache_dir,
        )


def schedule_command(args: argparse.Namespace) -> dict:
    config = _apply_email_gating(load_config(args.config_dir))
    week = args.week or str(just_completed_iso_week())
    with RunLedger(args.ledger) as ledger:
        summaries = run_weekly(
            config, ledger, iso_week=week, product_ids=args.products,
            dry_run=args.dry_run, force=args.force, offline=args.offline, cache_dir=args.cache_dir,
        )
    return {
        "iso_week": week,
        "email_mode": config.settings.email_mode,
        "products": len(summaries),
        "completed": sum(1 for s in summaries if s.status == "COMPLETED"),
        "skipped": sum(1 for s in summaries if s.status == "SKIPPED_ALREADY_COMPLETED"),
        "failed": sum(1 for s in summaries if s.status == "FAILED"),
        "runs": [s.model_dump() for s in summaries],
    }


def audit_command(args: argparse.Namespace) -> dict:
    parse_iso_week(args.week)
    with RunLedger(args.ledger) as ledger:
        record = ledger.get(args.product, args.week)
    if record is None:
        # X7.12 — clearly "no run", not an error.
        return {"product_id": args.product, "iso_week": args.week, "found": False, "status": "NO_RUN"}
    return {
        "found": True,
        "product_id": record.product_id,
        "iso_week": record.iso_week,
        "status": record.status,
        "run_id": record.run_id,
        "doc_id": record.doc_id,
        "section_anchor": record.section_anchor,
        "heading_id": record.heading_id,
        "deep_link": record.deep_link,
        "email_status": record.email_status,
        "message_id": record.message_id,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "metrics": record.metrics,
        "error": record.error,
    }


def ingest_command(args: argparse.Namespace) -> dict:
    from pulse.ingestion.cache import RawCache
    from pulse.ingestion.service import run_ingestion

    config = load_config(args.config_dir)
    product = config.registry.get(args.product)
    iso = parse_iso_week(args.week) if args.week else current_iso_week()

    result = run_ingestion(
        product,
        config.settings,
        iso,
        cache=RawCache(args.cache_dir),
        offline=args.offline,
    )
    out = {
        "product": product.id,
        "iso_week": str(iso),
        "window": [result.window_start, result.window_end],
        "source_counts": result.source_counts,
        "source_errors": result.source_errors,
        "stats": result.stats.model_dump(),
    }
    if args.show:
        out["sample"] = [
            {"source": r.source, "rating": r.rating, "lang": r.lang, "body": r.body}
            for r in result.reviews[: args.show]
        ]
    return out


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        if args.command == "run":
            summary = run_command(args)
            print(json.dumps(summary.model_dump(), indent=2, default=str))
            return 0 if summary.status != "FAILED" else 1
        if args.command == "schedule":
            result = schedule_command(args)
            print(json.dumps(result, indent=2, default=str))
            return 0 if result["failed"] == 0 else 1
        if args.command == "audit":
            result = audit_command(args)
            print(json.dumps(result, indent=2, default=str))
            return 0
        if args.command == "ingest":
            print(json.dumps(ingest_command(args), indent=2, default=str))
            return 0
    except IsoWeekError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RunInProgressError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
