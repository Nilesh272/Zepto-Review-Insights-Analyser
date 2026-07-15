"""CLI entry point (architecture §9).

Subcommands:
  run     — full agent run for a product + ISO week (Phase 0 loop; MCP tools still stubs).
  ingest  — Phase 1 only: fetch + normalize + filter reviews and print ingestion stats.

Backfill of arbitrary ISO weeks works via ``--week``; scheduling arrives in Phase 7.

Usage:
    python -m pulse.cli run --product groww --week 2026-W26 --dry-run
    python -m pulse.cli ingest --product groww --week 2026-W26 [--offline]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pulse.agent.core import AgentCore, RunSummary
from pulse.config import load_config
from pulse.state.ledger import RunInProgressError, RunLedger
from pulse.utils.isoweek import IsoWeekError, current_iso_week, parse_iso_week

_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_DEFAULT_LEDGER = ".pulse/ledger.db"
_DEFAULT_CACHE = ".pulse/cache"


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
    return parser


def run_command(args: argparse.Namespace) -> RunSummary:
    config = load_config(args.config_dir)
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
