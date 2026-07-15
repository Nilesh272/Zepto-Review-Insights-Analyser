# Phase 5 — Rendering

Self-contained snapshot of the agent through **Phase 5** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes Phases 0–4). The
`render_report` skill tool is now **real**: it turns grounded `Theme[]` into (a) Google Docs
`batchUpdate` requests for a new dated, anchored section and (b) a teaser email (HTML + text)
with a deep-link placeholder. **No live MCP calls** happen here — delivery (and filling the
deep link) lands in Phase 6.

## What's new vs Phase 4

| Area | Module | Architecture ref |
|---|---|---|
| Docs `batchUpdate` builder + contract validator | `pulse/render/docs.py` | §3.2, §8.1 |
| Teaser email (HTML + text, deep-link slot) | `pulse/render/email.py` | §7.3 |
| Real `render_report` tool | `pulse/agent/tools.py` | §3.2 |
| `EmailDraft` / `RenderedReport` contracts + `RenderConfig` | `pulse/models.py`, `pulse/config.py` | §5 |

## What it produces

`render_report` reads the grounded `themes` (and the `low_signal` flag) and builds a
`RenderedReport`:

- **Docs requests** — an ordered `batchUpdate` list: a dated `HEADING_1` carrying the stable
  **named-range anchor**, then per theme a `HEADING_2` title, summary, verbatim quote bullets,
  action bullets, and a "who this helps" line. Requests are emitted top-to-bottom with a running
  insertion index so the heading/anchor precede the body.
- **Teaser email** — top theme **titles** as bullets plus a "Read full report" link; an HTML part
  and a self-sufficient plain-text part. It is a teaser, **not** the full report.

### Anchor (idempotency, architecture §8.1)

```
pulse-<product-slug>-<iso_year>-W<ww>     e.g. pulse-groww-2026-W26
```

Deterministic and collision-free across weeks; product names are slugified.

## Safety / fidelity properties

- **Quote fidelity:** quotes are inserted **verbatim** — only summaries/titles are length-capped,
  never quote text (E5.8 / X5.12).
- **Escaping:** dynamic text is HTML-escaped in the email; Docs inserts are literal text (not
  corrupted), including emoji/unicode (X5.4 / X5.5 / X5.9).
- **Deep link:** the email carries a placeholder and is flagged unfilled until Phase 6 fills it
  after the Doc write (E5.7 / X5.9).
- **Low-signal weeks:** still render a clear, dated, anchored section and a matching email (X5.1).
- **One-page discipline:** themes capped to top-N, quotes capped per theme, long summaries
  truncated (E5.4 / X5.3 / X5.10).

## Setup / test

```bash
cd phase-5-rendering
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest                  # contract + snapshot-style + unit; no network, no MCP
```

## Notes
- The Docs request **contract** is validated by `validate_docs_requests` (a faked schema gate);
  the real Docs MCP `batchUpdate` is wired in Phase 6.
- `render/email.py` exposes `fill_deep_link()` / `has_unfilled_deep_link()` for Phase 6 to inject
  the real heading deep link after appending the section.
