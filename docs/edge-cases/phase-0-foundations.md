# Phase 0 — Foundations & Scaffolding — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 0. Each has an
> expected handling; covered by the Phase 0 evaluation suite where testable.

| ID | Edge case | Expected handling |
|---|---|---|
| X0.1 | Malformed ISO week (`2026-W00`, `2026-W54`, `2026-13`) | Reject with clear error before any work |
| X0.2 | ISO week 53 in a 53-week year vs 52-week year | Correctly accept/reject per ISO-8601 calendar |
| X0.3 | Unknown product id (not in registry) | Fail fast with list of valid products |
| X0.4 | Missing/!readable config file | Clear startup error; no partial run |
| X0.5 | Config present but missing required keys | Validation error naming the missing key |
| X0.6 | Optional keys omitted | Defaults applied (window, top-N, lang, EMAIL_MODE=draft) |
| X0.7 | Ledger file missing on first run | Auto-create empty ledger |
| X0.8 | Ledger corrupted / partial write | Detect, refuse to silently overwrite; surface error |
| X0.9 | Concurrent runs of same `(product, week)` | Lock/guard so only one acquires RUNNING; other no-ops or waits |
| X0.10 | Crash mid-run leaves status RUNNING | Stale-RUNNING detection allows safe re-run |
| X0.11 | Clock/timezone ambiguity (IST vs UTC) | Canonicalize to UTC internally; IST only for schedule trigger |
| X0.12 | Tool registry name collision | Reject duplicate tool registration at startup |
| X0.13 | Budget cap set to 0 / negative | Reject invalid config |
| X0.14 | Very large product registry | Loads without unbounded memory |
