# Phase 7 — Orchestration, Scheduling & Observability

Self-contained snapshot of the agent through **Phase 7** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes Phases 0–6) — the
**final** phase. The full agent loop now runs on a **weekly schedule** across all configured
products with **failure isolation**, emits **run metrics**, supports **backfill** of historic
weeks, answers **audit** queries ("what was sent when, for which week?"), and gates email
sending fail-safe via `EMAIL_MODE`.

## What's new vs Phase 6

| Area | Module | Architecture ref |
|---|---|---|
| Weekly scheduler (just-completed ISO week in IST, failure isolation) | `pulse/scheduler.py` | §9, §4 |
| Per-run metrics (reviews, clusters, quotes, tokens, cost, latency) | `pulse/agent/core.py` `_build_metrics` | §12 |
| Partial metrics on failed/halted runs | `pulse/agent/core.py` `_fail` | §12 |
| `schedule` + `audit` CLI subcommands | `pulse/cli.py` | §9 |
| `EMAIL_MODE` fail-safe send gating | `pulse/cli.py` `resolve_email_mode` | §7.3 |

## Orchestration flow

1. **Schedule** (`cli schedule`) computes the **just-completed ISO week** from the current time
   in **IST** (cadence is "Monday morning IST"); internal timestamps stay UTC. ISO-calendar
   arithmetic handles the year boundary (W52/W53 → W01); India has no DST so the offset is exact.
2. Each configured product runs the full agent loop. A failure in one product is **isolated** —
   it is marked `FAILED` while the others still complete.
3. **Backfill** any historic week with `cli run --week YYYY-Www`; idempotency holds against both
   the ledger and the Doc anchor.
4. **Metrics** are recorded on every run (including partial metrics for budget-halted/failed
   runs) and surfaced via the run summary and the ledger.
5. **Audit** (`cli audit --product … --week …`) returns the delivery identifiers
   (`doc_id`, `heading_id`, `deep_link`, `message_id`), status, timestamps, and metrics — or a
   clear `NO_RUN` for a week that never ran.

## Email send gating (fail-safe)

`EMAIL_MODE` overrides `settings.email_mode` and is **fail-safe**: only an explicit
`EMAIL_MODE=send` enables sending. Anything else — unset *(uses config)*, `draft`, or a typo —
resolves to a safe **draft** (a misconfiguration is logged). Dev/staging never sends by accident.

## Delivery transports (`mcp.transport`)

| Transport | What it does | Needs |
|---|---|---|
| `mock` | in-memory fake Docs/Gmail (tests/dev); nothing persisted | nothing |
| `local` *(default in `settings.yaml`)* | **writes a real HTML doc** to `out/docs/<doc_id>.html` + emails to `out/emails/` | nothing |
| `stdio` | appends to an actual **Google Doc** via a Google Docs/Gmail MCP server | a running MCP server + OAuth (see `STDIO_MCP_SETUP.md`) |

`local` is the zero-setup way to actually see reviews written into a document. For a real Google
Doc, switch to `stdio` and follow [`STDIO_MCP_SETUP.md`](STDIO_MCP_SETUP.md).

## Deploy to Vercel (public URL)

The pulse HTML is static and can be hosted on [Vercel](https://vercel.com) for a shareable link.

**One-time setup:**

```bash
cd phase-7-orchestration
npm i -g vercel          # or use: npx vercel
vercel login
vercel link              # create/link a Vercel project (interactive)
```

**Deploy manually:**

```bash
bash scripts/deploy_vercel.sh
```

Vercel serves `out/docs/` — the root URL `/` rewrites to `spotify-weekly-pulse.html`.

**Auto-deploy after each Monday run:** set `PULSE_VERCEL_DEPLOY=1` before the weekly job runs
(e.g. in `scripts/run_weekly.sh` or the launchd plist `EnvironmentVariables`).

> **Privacy:** a public Vercel URL exposes real review quotes. Use a private team project or
> Vercel password protection (Pro) for internal-only sharing.

## Setup / test

```bash
cd phase-7-orchestration
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                       # full loop + scheduling + audit + gating; no network

# Write a real doc for Spotify (transport: local) — open out/docs/<doc_id>.html afterwards:
python -m pulse.cli --ledger /tmp/pulse.db run --product spotify --week 2026-W26 --offline

# Weekly batch for the just-completed ISO week across all configured products:
python -m pulse.cli --ledger /tmp/pulse.db schedule --offline

# Audit what was delivered:
python -m pulse.cli --ledger /tmp/pulse.db audit --product spotify --week 2026-W26
```

## Notes
- **Idempotency** is enforced both by the ledger short-circuit on `(product, iso_week)` and the
  Doc-side anchor pre-check; reruns and schedule retriggers create **0** duplicate sections/sends.
- **Partial success** (Doc appended, email failed) is recorded as a split state; re-running
  completes the email only, without duplicating the section.
- **Retries:** transient MCP/network failures retry with backoff; an eventual failure marks the
  run `FAILED` and is safe to re-run.
- Real delivery to Google requires running Docs/Gmail MCP servers and `transport: stdio`.
