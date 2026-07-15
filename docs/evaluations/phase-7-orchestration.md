# Phase 7 — Orchestration, Scheduling & Observability — Evaluations

> Verifies the full agent loop, scheduling, backfill, and audit from
> [`implementationPlan.md`](../implementationPlan.md) Phase 7.

## Scope under test
Agent core full loop (§4), `scheduler.py`, `cli.py` (backfill/force/dry-run/EMAIL_MODE),
observability + audit (§12).

## Test types
- **End-to-end:** full pipeline product run (mock MCP + recorded sources).
- **Scheduling:** multi-product weekly run; failure isolation.
- **Audit:** query "what was sent when, for which week?".

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E7.1 | E2E grounded pulse | Run product end-to-end | One-page pulse w/ validated quotes appended to Doc + email drafted/sent via MCP |
| E7.2 | E2E idempotency | Re-run same product+week | No duplicate section/send; ledger shows COMPLETED |
| E7.3 | Weekly schedule | Trigger cron for all 5 products | Each processed for the just-completed ISO week |
| E7.4 | Failure isolation | Force one product to fail | That product `FAILED`; others COMPLETED |
| E7.5 | Retry/backoff | Inject transient MCP/LLM errors | Retried; succeeds or safe `FAILED` |
| E7.6 | Backfill | `cli run --week 2026-W21` | Historic week produced; idempotent vs ledger+anchor |
| E7.7 | Budget enforcement | Near-cap run | Halts within caps; recorded in metrics |
| E7.8 | Dry-run | `--dry-run` full loop | No MCP writes; renders printed |
| E7.9 | Send gating | `EMAIL_MODE` default | Dev/staging draft-only unless explicitly `send` |
| E7.10 | Audit query | Query ledger by product+week | Returns `doc_id, heading_id, deep_link, message_id`, timestamps, metrics |
| E7.11 | Metrics emitted | Inspect run metrics | reviews_in, clusters, quotes validated/dropped, tokens, cost, latency present |

## Metrics / targets
- E2E success on all configured products in staging.
- Idempotency holds across reruns and schedule retriggers.
- Audit answers the "what/when/which week" question for every run.

## Definition of done
All E7.* pass; staging E2E green for all products; scheduling, backfill, audit, and gating
behave per spec.
