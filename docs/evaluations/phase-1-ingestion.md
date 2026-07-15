# Phase 1 — Ingestion (`fetch_reviews`) — Evaluations

> Verifies App Store + Play ingestion, normalization, dedup, and windowing from
> [`implementationPlan.md`](../implementationPlan.md) Phase 1.

## Scope under test
`ingestion/appstore.py`, `ingestion/playstore.py`, `ingestion/normalize.py`, the
`fetch_reviews` skill tool, and fetch caching.

## Test types
- **Unit:** RSS/scraper parsers against saved fixtures (recorded responses).
- **Contract:** parser output conforms to `RawReview`; normalizer output to
  `NormalizedReview`.
- **Replay:** cached inputs produce identical outputs (backfill determinism).

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E1.1 | App Store RSS parse | Parse fixture RSS pages | All fields mapped; ratings 1–5; UTC timestamps |
| E1.2 | Play scraper parse | Parse fixture scraper payloads | Fields mapped; locale/version captured when present |
| E1.3 | Pagination | Multi-page fixtures | All pages consumed; no dropped/duplicated pages |
| E1.4 | Source merge | Combine App Store + Play | Union with `source` tag preserved |
| E1.5 | Exact dedup | Inject duplicate `(source, review_id)` | One copy retained |
| E1.6 | Near-dup dedup | Inject minor text variants | Near-dups collapsed via text hash; distinct reviews kept |
| E1.7 | Window filter (8–12w) | Reviews spanning before/within/after window | Only in-window retained; ISO boundary inclusive-correct |
| E1.8 | Determinism / replay | Re-run against cache | Byte-identical `NormalizedReview[]` ordering |
| E1.9 | Per-product coverage | Run all 5 products | Non-empty result where reviews exist; clean empty otherwise |

## Metrics / targets
- Parser field-mapping accuracy 100% on fixtures.
- Dedup precision/recall ≥ 0.95 on the labeled dup fixture.
- Window off-by-one defects: 0.

## Definition of done
All E1.* pass on fixtures; replay is deterministic; no live network needed in CI (recorded
fixtures).
