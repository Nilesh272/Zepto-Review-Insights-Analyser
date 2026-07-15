# Weekly Product Review Pulse — Implementation Plan

> Companion to [`problemStatement.md`](./problemStatement.md) and
> [`architecture.md`](./architecture.md). This plan delivers the **AI agent** incrementally,
> one architecture layer per phase, each with explicit **exit criteria**. Every phase has a
> matching evaluations file (`docs/evaluations/phase-N-*.md`) and an edge-case file
> (`docs/edge-cases/phase-N-*.md`).

---

## How to read this plan

- **Phases are vertical-ish slices** of the agent: each ends in something runnable or
  testable, not just code.
- **Each phase exposes one or more tools** to the agent core (skill tools) or wires an MCP
  tool (delivery), matching §3 of the architecture.
- **Gate to advance:** a phase is "done" only when its exit criteria pass *and* its
  evaluation suite + edge-case checks are green.
- **Delivery posture:** every phase that can write to Google Workspace defaults to
  **dry-run / draft-only** until Phase 7 explicitly enables sending.

### Phase overview

| Phase | Name | Architecture refs | Primary artifact |
|---|---|---|---|
| 0 | Foundations & Scaffolding | §3.1, §5, §8.2, §10 | Agent core skeleton, config, models, ledger, CLI dry-run |
| 1 | Ingestion | §3.2 `fetch_reviews`, §2 | App Store + Play ingestion, normalize/dedup/window |
| 2 | Preprocessing & Safety | §3.2 `scrub_pii`, §11 | PII scrubbing + language filter |
| 3 | Clustering | §3.2 `cluster_reviews`, §6 | Embeddings + UMAP + HDBSCAN + ranking |
| 4 | Summarization & Grounding | §3.2 `summarize_clusters`/`validate_quotes`, §6 | LLM themes/quotes/actions + quote validation gate |
| 5 | Rendering | §3.2 `render_report`, §7.3 | Docs `batchUpdate` requests + email (HTML/text) + deep link |
| 6 | MCP Delivery & Idempotency | §3.3, §7, §8 | Docs MCP append + Gmail MCP draft/send + anchors + ledger |
| 7 | Orchestration, Scheduling & Observability | §3.1, §4, §9, §12 | Full agent loop, cron, backfill, metrics, audit, E2E |

---

## Phase 0 — Foundations & Scaffolding

**Goal:** a runnable agent skeleton that can plan a (no-op) run, with all typed contracts,
config, and the run ledger in place.

**Scope**
- Repo layout per architecture §14 (`src/pulse/...`).
- Typed data contracts (§5): `RawReview`, `CleanReview`, `Cluster`, `Theme`, `Quote`,
  `RunRecord`.
- Config loaders: `config/products.yaml`, `config/settings.yaml` (window, top-N, language
  allowlist, cost/token caps, `EMAIL_MODE`, MCP endpoints, per-product Doc id).
- Agent core skeleton (§3.1): planner + tool dispatcher + tool registry (registers stub
  tools), per-run cost/token budget object.
- Run ledger (§8.2) with `(product, iso_week)` key; statuses `RUNNING/COMPLETED/FAILED`.
- `cli.py` with `run --product --week --dry-run`; ISO-week parsing/validation.

**Out of scope:** real ingestion, LLM, MCP calls (use stubs/fakes).

**Exit criteria**
- `cli run --product groww --week 2026-W26 --dry-run` plans and dispatches stub tools, writes
  a `RUNNING`→`COMPLETED` ledger record, prints a run summary.
- Re-running the same product+week is detected as already-complete (idempotency short-circuit
  scaffolding works against the ledger).
- All data contracts validate (round-trip serialize/deserialize) in unit tests.
- Eval suite `phase-0` green; edge cases `phase-0` handled.

---

## Phase 1 — Ingestion (`fetch_reviews`)

**Goal:** reliably fetch and normalize public reviews from both stores for a product/window.

**Scope**
- `ingestion/appstore.py`: iTunes customer-reviews RSS, paginate, parse → `RawReview`.
- `ingestion/playstore.py`: Play scraper with pagination + backoff → `RawReview`.
- `ingestion/normalize.py`: merge sources; dedup by `(source, review_id)` and near-dup text
  hash; filter to the configured 8–12 week window; UTC timestamps.
- Register as the `fetch_reviews` skill tool.
- Caching of raw fetches for reproducible reruns/backfill.

**Exit criteria**
- For each supported product, agent fetches a non-empty `NormalizedReview[]` for a recent
  window from both stores (where reviews exist).
- Dedup removes exact + near-duplicate reviews; window filter is inclusive/correct at ISO
  boundaries.
- Deterministic given cached inputs (replayable for backfill).
- Eval suite `phase-1` green; edge cases `phase-1` handled.

---

## Phase 2 — Preprocessing & Safety (`scrub_pii`)

**Goal:** clean, language-filtered, PII-free review text ready for embeddings/LLM.

**Scope**
- `preprocess/language.py`: language detection + allowlist filter (default `en`); flag others.
- `preprocess/pii.py`: redact emails, phone numbers, person names, account/card-like numbers;
  record `pii_spans` for audit; produce `body_clean`.
- Wire into the `scrub_pii` tool; PII scrubbing happens **before** embeddings, LLM, and
  publish.

**Exit criteria**
- No raw PII passes downstream: a corpus seeded with synthetic PII shows 0 leaks in
  `body_clean` and in any rendered output.
- Language filter keeps target languages and flags/excludes others without dropping valid
  English reviews.
- `pii_spans` audit is accurate (redaction offsets correct).
- Eval suite `phase-2` green; edge cases `phase-2` handled.

---

## Phase 3 — Clustering (`cluster_reviews`)

**Goal:** group semantically similar reviews and rank clusters for summarization.

**Scope**
- `reasoning/embed.py`: batched + cached embeddings of `body_clean`.
- `reasoning/cluster.py`: UMAP dimensionality reduction → HDBSCAN density clustering; handle
  the HDBSCAN noise label; rank clusters by `size × recency × rating spread`.
- Output `Cluster[]` with stable ordering; expose top-N selection.
- Register as the `cluster_reviews` skill tool.

**Exit criteria**
- On a labeled fixture set, clusters are coherent (intra-cluster similarity high, themes
  separable); ranking surfaces the expected top themes.
- Deterministic clustering given fixed seeds/inputs (reproducible runs).
- Graceful behavior when most points are noise or when only 1 cluster forms.
- Eval suite `phase-3` green; edge cases `phase-3` handled.

---

## Phase 4 — Summarization & Grounding (`summarize_clusters`, `validate_quotes`)

**Goal:** LLM produces named themes, candidate quotes, actions, "who this helps" — and every
published quote is **validated against real review text**.

**Scope**
- `reasoning/summarize.py`: per top-N cluster, prompt the LLM with clustered evidence inside a
  clearly delimited **untrusted data** block; produce `ThemeDraft` (title, summary, candidate
  quotes w/ source `review_id`, actions, who-this-helps).
- `reasoning/validate.py`: hard gate — keep a quote only if exact/high-similarity fuzzy match
  to an actual review body; drop unverifiable quotes; attach provenance.
- Enforce per-run token/cost caps via the agent core budget.
- Prompt-injection defense: system prompt forbids following instructions in review text.

**Exit criteria**
- 100% of published quotes pass validation (zero hallucinated quotes in output).
- Themes/actions are non-empty and coherent for fixtures with clear signal; "low-signal"
  handling when clusters are weak.
- Injection-laced fixtures do not alter agent behavior or output structure.
- Token/cost stays within configured caps.
- Eval suite `phase-4` green; edge cases `phase-4` handled.

---

## Phase 5 — Rendering (`render_report`)

**Goal:** turn grounded themes into (a) Google Docs `batchUpdate` requests for a new dated
section and (b) a teaser email (HTML + text) with a deep link placeholder.

**Scope**
- `render/docs.py`: build `batchUpdate` requests — dated heading carrying the stable anchor
  (§8.1), top themes, validated quotes, action ideas, "who this helps".
- `render/email.py`: teaser email (top themes as bullets) + "Read full report" button; HTML
  and plain-text parts; deep-link slot filled after the Doc write.
- One-page layout discipline (concise narrative per problem statement sample output).
- Register as the `render_report` skill tool.

**Exit criteria**
- Rendered Docs requests are schema-valid and produce the expected section structure in a
  fake/contract test.
- Email renders valid multipart HTML + text; teaser only (not a full duplicate report);
  contains a deep-link placeholder.
- Anchor string is deterministic for `(product, iso_week)`.
- Eval suite `phase-5` green; edge cases `phase-5` handled.

---

## Phase 6 — MCP Delivery & Idempotency

**Goal:** deliver **only** through MCP tools, append to the running Doc, send/draft the email,
and guarantee idempotency per `(product, iso_week)`.

**Scope**
- `delivery/docs_mcp.py` (`docs_mcp.append_section`): call Google Docs MCP `get_document` to
  check the anchor, then `batch_update` to append; capture `doc_id`, `heading_id`, deep link.
- `delivery/gmail_mcp.py` (`gmail_mcp.draft_or_send`): Gmail MCP `create_draft` (dev/staging)
  or `send_message` (prod); capture `message_id`.
- Idempotency: skip Doc append if anchor exists (unless `--force`); skip email if ledger shows
  `draft`/`sent` (§8.3).
- No Google SDK imports outside MCP servers; OAuth lives in MCP server config (§10).
- Deep link injected into email after the Doc write.

**Exit criteria**
- Real (or contract-faked) MCP calls append exactly one dated section and create/send exactly
  one email per `(product, iso_week)`.
- Re-running the same product+week creates **no** duplicate section and **no** duplicate send.
- Ledger records `doc_id`, `section_anchor`, `heading_id`, `deep_link`, `email_status`,
  `message_id`.
- Static check: no `googleapiclient`/Google SDK import outside `delivery/`→MCP boundary.
- Eval suite `phase-6` green; edge cases `phase-6` handled.

---

## Phase 7 — Orchestration, Scheduling & Observability

**Goal:** the complete, schedulable AI agent with auditability and end-to-end runs.

**Scope**
- Agent core full loop (§4): plan → skill tools → MCP delivery → ledger, with retries/backoff
  on transient tool/MCP errors and budget enforcement.
- `scheduler.py`: weekly cron (Monday morning IST) across all configured products for the
  just-completed ISO week.
- `cli.py`: backfill any ISO week; `--dry-run`; `--force`; `EMAIL_MODE=draft|send` gating
  (send requires explicit enablement).
- Observability (§12): structured per-tool logs, metrics (reviews in, clusters, quotes
  validated/dropped, tokens, cost, latency), and a queryable audit answering "what was sent
  when, for which week?".

**Exit criteria**
- A full E2E run for a configured product produces a grounded one-page pulse, appends it to
  the product Doc via MCP, and drafts/sends the teaser email via MCP — idempotently.
- Scheduled run processes all configured products; failures isolate per product and mark
  `FAILED` without blocking others.
- Backfill of a historic ISO week is idempotent against ledger + anchor.
- Audit query returns delivery identifiers + metadata per run.
- Eval suite `phase-7` green; edge cases `phase-7` handled.

---

## Cross-cutting acceptance (maps to problem-statement success criteria)

- **Grounded one-page pulse** for a configured product/window — Phases 4–5, verified in 7.
- **Idempotent per product + week** — Phase 6, verified end-to-end in 7.
- **Traceability** — this plan + the §15 table in `architecture.md`; each requirement maps to
  a phase, a tool/MCP usage, and exit criteria above.

## Evaluation & edge-case index

| Phase | Evaluations | Edge cases |
|---|---|---|
| 0 | `docs/evaluations/phase-0-foundations.md` | `docs/edge-cases/phase-0-foundations.md` |
| 1 | `docs/evaluations/phase-1-ingestion.md` | `docs/edge-cases/phase-1-ingestion.md` |
| 2 | `docs/evaluations/phase-2-preprocessing.md` | `docs/edge-cases/phase-2-preprocessing.md` |
| 3 | `docs/evaluations/phase-3-clustering.md` | `docs/edge-cases/phase-3-clustering.md` |
| 4 | `docs/evaluations/phase-4-summarization-grounding.md` | `docs/edge-cases/phase-4-summarization-grounding.md` |
| 5 | `docs/evaluations/phase-5-rendering.md` | `docs/edge-cases/phase-5-rendering.md` |
| 6 | `docs/evaluations/phase-6-mcp-delivery.md` | `docs/edge-cases/phase-6-mcp-delivery.md` |
| 7 | `docs/evaluations/phase-7-orchestration.md` | `docs/edge-cases/phase-7-orchestration.md` |
