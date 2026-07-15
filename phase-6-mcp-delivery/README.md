# Phase 6 — MCP Delivery & Idempotency

Self-contained snapshot of the agent through **Phase 6** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes Phases 0–5). The two
**MCP delivery tools** are now real: `docs_append_section` appends the week's section to the
product's running Google Doc via the **Google Docs MCP**, and `gmail_draft_or_send` drafts/sends
the teaser email via the **Gmail MCP** — with idempotency guaranteed per `(product, iso_week)`.

## What's new vs Phase 5

| Area | Module | Architecture ref |
|---|---|---|
| MCP client interfaces, errors, transient retry | `pulse/delivery/mcp_client.py` | §7 |
| In-process fake MCP servers (Docs + Gmail) | `pulse/delivery/mock_mcp.py` | §7 |
| Real transport placeholder (stdio) | `pulse/delivery/stdio_mcp.py` | §7 |
| `docs_mcp.append_section` (anchor pre-check, force replace) | `pulse/delivery/docs_mcp.py` | §3.3, §8.1 |
| `gmail_mcp.draft_or_send` (deep link, recipients, idempotency) | `pulse/delivery/gmail_mcp.py` | §3.3, §7.3 |
| Ledger delivery fields + prior-state reconciliation | `pulse/agent/core.py` | §8.2 |

## Delivery flow (architecture §8.3)

1. The agent core short-circuits if the ledger shows the run already `COMPLETED` (idempotent
   no-op), and passes any prior delivery state into the run for reconciliation.
2. `docs_append_section` calls `get_document` to check the **stable anchor**
   (`pulse-<product>-<year>-W<ww>`):
   - anchor present, no `--force` → **skip** the append, reuse the existing heading/deep link;
   - anchor present, `--force` → **delete + re-append** (clean replace, never a duplicate);
   - absent → append exactly one dated section.
   It returns `doc_id`, `heading_id`, and the heading **deep link**.
3. `gmail_draft_or_send` injects the deep link into the teaser, validates recipients, and (per
   `email_mode`) **drafts** (dev/staging) or **sends** (prod) exactly once — skipping if the
   ledger already recorded a draft/send.
4. The ledger records `doc_id`, `section_anchor`, `heading_id`, `deep_link`, `email_status`,
   `message_id`.

## MCP-only boundary

`pulse/delivery/` is the **only** package that speaks MCP. The agent holds no Google
credentials and imports **no Google SDK anywhere** — OAuth lives inside the MCP servers. A
static test (`tests/test_mcp_boundary.py`) fails the build if a Google SDK import appears.

### Transport

`settings.mcp.transport`:
- `mock` *(default)* — in-process fake Docs/Gmail servers, so local/dev runs and the full test
  suite exercise real delivery logic and idempotency offline, with no external server.
- `stdio` — a real MCP server over the configured endpoint (deployment integration point in
  `stdio_mcp.py`; requires an MCP client SDK). Switching transports touches only `delivery/`.

## Setup / test

```bash
cd phase-6-mcp-delivery
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                  # mock-MCP contract + idempotency + boundary; no network

# End-to-end via the mock transport (drafts a teaser, appends one section):
python -m pulse.cli --ledger /tmp/pulse.db run --product groww --week 2026-W26 --offline
```

## Notes
- **Idempotency** is enforced twice over: the ledger short-circuit on `(product, iso_week)`, and
  the Doc-side anchor pre-check. Re-runs create **0** duplicate sections and **0** duplicate sends.
- **Retries:** transient MCP failures are retried with exponential backoff; auth/not-found errors
  fail fast with no REST fallback. An eventual failure marks the run `FAILED` and is safe to re-run.
- **Recipients:** invalid/empty recipient lists are skipped + flagged, never error-sent.
- Real delivery to Google requires running Docs/Gmail MCP servers and `transport: stdio`.
