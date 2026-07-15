# Phase 1 — Ingestion (`fetch_reviews`) — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 1.

| ID | Edge case | Expected handling |
|---|---|---|
| X1.1 | Store returns 0 reviews for the window | Return empty set cleanly; downstream emits "low-signal" later |
| X1.2 | App Store RSS unavailable / 5xx | Retry w/ backoff; on persistent failure, mark source failed, continue with other source |
| X1.3 | Play scraper blocked / rate-limited (429) | Backoff + jitter; respect limits; partial results flagged |
| X1.4 | Pagination cursor breaks mid-way | Resume/abort cleanly; never silently truncate without flag |
| X1.5 | Duplicate review ids across pages | Deduped by `(source, review_id)` |
| X1.6 | Near-duplicate text (bot/spam reposts) | Collapsed via text-hash near-dup detection |
| X1.7 | Missing fields (no title/version/author) | Tolerate nulls; required fields validated |
| X1.8 | Non-UTC / malformed timestamps | Normalize to UTC; drop/flag unparseable dates |
| X1.9 | Reviews exactly on ISO window boundary | Inclusive rule applied consistently (no off-by-one) |
| X1.10 | Mixed locales / non-English text | Pass through; language handled in Phase 2 |
| X1.11 | Emoji / RTL / unusual unicode | Preserved without corruption |
| X1.12 | Extremely long review body | Accepted; bounded for downstream token budget |
| X1.13 | Source schema change (fields renamed) | Parser fails loudly with diagnostic, not silent empties |
| X1.14 | Wrong app id / package (product misconfig) | Detect empty/foreign results; surface config warning |
| X1.15 | Network flake mid-fetch | Cache partials; resume deterministically on replay |
