# Phase 0 — Foundations & Scaffolding — Evaluations

> Verifies the agent skeleton, typed contracts, config, and run ledger from
> [`implementationPlan.md`](../implementationPlan.md) Phase 0.

## Scope under test
Agent core skeleton (planner, tool dispatcher, tool registry, budget), data contracts (§5),
config loaders, run ledger (§8.2), CLI dry-run.

## Test types
- **Unit:** models, config parsing, ledger CRUD, ISO-week parsing.
- **Contract:** tool registry registers/dispatches stub tools with typed I/O.
- **Smoke:** `cli run ... --dry-run` end-to-end with stubs.

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E0.1 | Data contracts round-trip | Serialize→deserialize each model with valid + boundary values | Lossless; validation errors on bad input |
| E0.2 | Config load defaults | Load `settings.yaml` with omitted optional keys | Defaults applied: window 8–12w, top-N 3–5, lang `en`, `EMAIL_MODE=draft` |
| E0.3 | Product registry | Load `products.yaml` for all 5 products | Each has App Store id + Play package + Doc id |
| E0.4 | Ledger lifecycle | Create→RUNNING→COMPLETED; read by `(product, iso_week)` | Status transitions persist; key lookup correct |
| E0.5 | Idempotency short-circuit | Run twice with same key against ledger | 2nd run detected COMPLETED, no re-dispatch |
| E0.6 | ISO-week parsing | Parse `2026-W01`, `2026-W26`, `2026-W53` | Correct year/week; rejects malformed |
| E0.7 | Tool dispatch | Register stub tool, dispatch via core | Typed result returned; logged |
| E0.8 | Budget object | Configure token/cost cap, simulate usage | Over-cap raises/halts before next tool |
| E0.9 | Dry-run smoke | `cli run --product groww --week 2026-W26 --dry-run` | Plans, dispatches stubs, writes ledger, prints summary, no external calls |

## Metrics / targets
- Unit + contract coverage of `models`, `state`, `agent/registry` ≥ 90%.
- Dry-run completes < 2s with stubs.

## Definition of done
All E0.* pass in CI; dry-run is reproducible; no network/MCP/LLM calls occur in Phase 0.
