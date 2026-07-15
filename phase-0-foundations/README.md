# Phase 0 — Foundations & Scaffolding

Runnable AI-agent skeleton for the Weekly Product Review Pulse. Implements Phase 0 of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) against
[`../docs/architecture.md`](../docs/architecture.md).

## What's here

| Area | Module | Architecture ref |
|---|---|---|
| Typed data contracts | `pulse/models.py` | §5 |
| Config + product registry | `pulse/config.py`, `config/*.yaml` | §10 |
| ISO-week parsing | `pulse/utils/isoweek.py` | §9 |
| Run ledger (SQLite) | `pulse/state/ledger.py` | §8.2 |
| Agent core (planner + dispatcher) | `pulse/agent/core.py` | §3.1 |
| Tool registry | `pulse/agent/registry.py` | §3.1 |
| Per-run budget | `pulse/agent/budget.py` | §11 |
| Stub tools (skill + MCP) | `pulse/agent/tools.py` | §3.2, §3.3 |
| CLI (dry-run) | `pulse/cli.py` | §9 |

> Phase 0 wires the skeleton only: all tools are **stubs**. Real ingestion, LLM, clustering,
> and MCP delivery arrive in later phases. No network, LLM, or MCP calls happen here.

## Setup

```bash
cd phase-0-foundations
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run a dry run

```bash
python -m pulse.cli run --product groww --week 2026-W26 --dry-run
```

Re-running the same product + week is detected as already complete (idempotency
short-circuit).

## Test

```bash
python -m pytest
```

## Notes

- `config/products.yaml` ids/doc ids are **placeholders** — replace with real store ids and
  per-product Google Doc ids before later phases.
- The ledger defaults to `./.pulse/ledger.db` (override with `--ledger`).
