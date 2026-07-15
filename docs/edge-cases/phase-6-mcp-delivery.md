# Phase 6 — MCP Delivery & Idempotency — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 6.

| ID | Edge case | Expected handling |
|---|---|---|
| X6.1 | Re-run same product+week | No duplicate Doc section; no duplicate email (anchor + ledger) |
| X6.2 | Anchor exists but body partially written (prior crash) | Detect partial; `--force` repair replaces cleanly, no dupes |
| X6.3 | Docs MCP `batch_update` partially applies | Treat as failed; mark FAILED; safe idempotent re-run |
| X6.4 | Doc not found / wrong Doc id | Fail fast with config diagnostic; no fallback to REST |
| X6.5 | MCP server unauthenticated / token expired | Surface auth error from MCP; agent does not hold/refresh Google creds |
| X6.6 | MCP server unreachable / timeout | Retry w/ backoff; eventual FAILED is re-runnable |
| X6.7 | Gmail MCP send succeeds but ledger write fails | Reconcile on next run via message-id/anchor; avoid double-send |
| X6.8 | `EMAIL_MODE=draft` in dev | Only a draft is created; nothing sent |
| X6.9 | Switching draft→send across runs | Idempotency prevents duplicate; defined transition policy |
| X6.10 | Deep link heading id changes on re-render | Anchor stable; link resolves to the correct section |
| X6.11 | Attempted direct Google SDK call | Blocked by design; static import scan fails the build |
| X6.12 | Concurrent delivery for same key | Lock ensures single append/send |
| X6.13 | Doc hits size/structure limits | Handle MCP error gracefully; flag for doc rotation policy |
| X6.14 | Recipient list empty/invalid | Validate before send; skip/flag rather than error-send |
