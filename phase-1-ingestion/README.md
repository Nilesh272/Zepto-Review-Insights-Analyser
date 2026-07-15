# Phase 1 — Ingestion

Self-contained snapshot of the agent through **Phase 1** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes the Phase 0
foundations). The `fetch_reviews` skill tool is now **real**: it pulls App Store + Google Play
reviews, normalizes, deduplicates, windows, and applies quality filters.

## What's new vs Phase 0

| Area | Module | Architecture ref |
|---|---|---|
| App Store ingestion (iTunes RSS JSON) | `pulse/ingestion/appstore.py` | §3.2 |
| Google Play ingestion (scraper) | `pulse/ingestion/playstore.py` | §3.2 |
| Raw fetch cache (replayable backfill) | `pulse/ingestion/cache.py` | §3.2 |
| Quality filters (emoji / language / length) | `pulse/ingestion/filters.py` | §3.2 |
| Merge + dedup + window | `pulse/ingestion/normalize.py` | §3.2 |
| Orchestration (per-source isolation) | `pulse/ingestion/service.py` | §3.2, §4 |
| Text utils (emoji, word count, fingerprint) | `pulse/utils/text.py` | — |
| Real `fetch_reviews` tool | `pulse/agent/tools.py` | §3.2 |
| `ingest` CLI command | `pulse/cli.py` | §9 |

## Quality filters (per request)

A review is **dropped** when it:
- contains any emoji (`filters.drop_emoji`)
- has fewer than `filters.min_words` words (default 4)
- is detected as a language not in `language_allowlist` (`filters.drop_other_languages`)

All three are toggleable in `config/settings.yaml`. The drop order is emoji → too-short →
language, and per-review drop reasons are tallied in the ingestion stats.

## Setup

```bash
cd phase-1-ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Ingest (Phase 1 only)

```bash
# Live fetch + filter, print stats:
python -m pulse.cli ingest --product groww --week 2026-W26 --show 5

# Replay from cache only (no network):
python -m pulse.cli ingest --product groww --week 2026-W26 --offline
```

## Full agent run (MCP tools still stubbed until Phase 6)

```bash
python -m pulse.cli run --product groww --week 2026-W26 --dry-run
```

## Test

```bash
python -m pytest          # fixtures-based; no network required
```

## Notes
- Live Google Play fetching needs the optional `google-play-scraper` (in `requirements.txt`).
- Language detection uses `langdetect` with a fixed seed for determinism.
- Raw fetches are cached under `--cache-dir` (default `.pulse/cache`) so backfill is replayable.
