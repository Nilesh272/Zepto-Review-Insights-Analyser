# Phase 5 — Rendering (`render_report`) — Evaluations

> Verifies Google Docs `batchUpdate` request building and email rendering from
> [`implementationPlan.md`](../implementationPlan.md) Phase 5.

## Scope under test
`render/docs.py`, `render/email.py`, the `render_report` tool, anchor generation.

## Test types
- **Contract:** Docs requests validate against the Docs `batchUpdate` request schema (faked).
- **Snapshot:** rendered Doc structure + email HTML/text vs approved snapshots.
- **Unit:** anchor determinism; deep-link placeholder.

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E5.1 | Docs request schema | Build batch for a sample report | All requests schema-valid |
| E5.2 | Section structure | Inspect generated heading + body | Dated heading w/ anchor, themes, quotes, actions, who-helps |
| E5.3 | Anchor determinism | Build twice for same `(product, week)` | Identical anchor `pulse-<product>-<year>-W<ww>` |
| E5.4 | One-page discipline | Length/heuristic check | Concise; matches sample-output shape |
| E5.5 | Email multipart | Render email | Valid HTML + plain-text alternative |
| E5.6 | Teaser only | Inspect email body | Top themes as bullets; **not** the full report |
| E5.7 | Deep-link slot | Inspect "Read full report" | Placeholder present, filled post-Doc-write in Phase 6 |
| E5.8 | Quote fidelity | Compare rendered quotes to validated quotes | Verbatim, no mutation |
| E5.9 | Escaping | Reviews with HTML/markdown chars | Properly escaped in HTML email + Docs text |

## Metrics / targets
- Docs request schema validity: 100%.
- Snapshot diffs reviewed and intentional only.
- Quote rendering mutation rate: 0.

## Definition of done
All E5.* pass; Docs/email render correctly against contract/snapshots; anchor is
deterministic; no live MCP calls yet.
