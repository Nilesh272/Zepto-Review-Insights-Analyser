# Phase 7 — Orchestration, Scheduling & Observability — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 7.

| ID | Edge case | Expected handling |
|---|---|---|
| X7.1 | One product fails in a weekly batch | Isolated FAILED; other products still COMPLETED |
| X7.2 | Scheduler fires twice (overlap/retry) | Idempotency prevents duplicate sections/sends |
| X7.3 | Run crashes mid-pipeline | Ledger left recoverable; re-run resumes idempotently |
| X7.4 | Backfill of an old week with stale data | Uses cached/recorded sources; idempotent vs anchor + ledger |
| X7.5 | DST / IST offset around schedule time | Trigger computed in IST; internal times UTC; no missed/double week |
| X7.6 | Year boundary (W52/W53 → W01) | Correct ISO-year+week selection; anchors unique |
| X7.7 | Transient LLM/MCP/network errors | Retries w/ backoff; bounded attempts; safe FAILED |
| X7.8 | Per-run budget exceeded | Halt within cap; record partial metrics; mark status accordingly |
| X7.9 | Long-running run vs schedule window | Runs don't overlap-clobber; locking per product+week |
| X7.10 | Config change mid-week (new product added) | Picked up next scheduled run; no retroactive duplicates |
| X7.11 | `EMAIL_MODE` misconfigured in prod | Default safe (draft) unless explicitly `send`; logged |
| X7.12 | Audit query for a week that never ran | Returns "no run" clearly, not an error |
| X7.13 | Partial success (Doc appended, email failed) | Ledger reflects split state; re-run completes email only, no dup section |
| X7.14 | Metrics/log sink unavailable | Run still completes; observability degrades gracefully |
| X7.15 | Dry-run accidentally in prod schedule | No MCP writes; clearly flagged so it's caught |
