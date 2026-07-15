# Phase 6 — MCP Delivery & Idempotency — Evaluations

> Verifies MCP-only delivery (Google Docs MCP + Gmail MCP) and idempotency from
> [`implementationPlan.md`](../implementationPlan.md) Phase 6.

## Scope under test
`delivery/docs_mcp.py` (`docs_mcp.append_section`), `delivery/gmail_mcp.py`
(`gmail_mcp.draft_or_send`), anchor existence checks, ledger updates, MCP boundary.

## Test types
- **Contract:** against a faked/mock MCP server implementing the used tools.
- **Idempotency:** repeated runs of same `(product, iso_week)`.
- **Static:** import-boundary check (no Google SDK outside MCP).
- **Integration (gated):** against a real MCP server in a sandbox Doc/mailbox.

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E6.1 | Append via MCP | `append_section` on fresh Doc | Exactly one dated section added; `heading_id` returned |
| E6.2 | Anchor pre-check | `get_document` before write | Existing anchor detected correctly |
| E6.3 | Doc idempotency | Re-run same week (no `--force`) | No duplicate section created |
| E6.4 | Force replace | Re-run with `--force` | Section replaced, not duplicated |
| E6.5 | Email draft (dev) | `EMAIL_MODE=draft` | Draft created; `message_id` captured; nothing sent |
| E6.6 | Email send (prod) | `EMAIL_MODE=send` | Exactly one send; `message_id` captured |
| E6.7 | Email idempotency | Re-run with ledger `sent/draft` | No duplicate send/draft |
| E6.8 | Deep link injection | Inspect delivered email | Link targets the new heading `...#heading=<id>` |
| E6.9 | Ledger completeness | After delivery | `doc_id, section_anchor, heading_id, deep_link, email_status, message_id` recorded |
| E6.10 | MCP-only boundary | Static import scan | No `googleapiclient`/Google SDK import outside `delivery/`→MCP |
| E6.11 | MCP error handling | Mock transient failure | Retried w/ backoff; eventual `FAILED` is safe to re-run |

## Metrics / targets
- Duplicate sections per repeated run: **0**.
- Duplicate sends per repeated run: **0**.
- Boundary violations: **0**.

## Definition of done
All E6.* pass against mock MCP (and a gated real-MCP smoke); idempotency and MCP-only delivery
proven.
