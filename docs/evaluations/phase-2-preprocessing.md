# Phase 2 — Preprocessing & Safety (`scrub_pii`) — Evaluations

> Verifies PII scrubbing and language filtering from
> [`implementationPlan.md`](../implementationPlan.md) Phase 2.

## Scope under test
`preprocess/pii.py`, `preprocess/language.py`, the `scrub_pii` tool.

## Test types
- **Unit:** redaction regex/NER on a synthetic-PII corpus.
- **Property:** no PII pattern survives in `body_clean`.
- **Contract:** `CleanReview.pii_spans` offsets map to redacted regions.

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E2.1 | Email redaction | Corpus with emails | 0 emails in `body_clean` |
| E2.2 | Phone redaction | Intl + local formats | 0 phone numbers remain |
| E2.3 | Person names | NER over seeded names | Names redacted; common app/feature words not over-redacted |
| E2.4 | Account/card-like numbers | Seeded PANs/account ids | All redacted |
| E2.5 | Span audit accuracy | Compare `pii_spans` to known offsets | Offsets correct; reversible mapping |
| E2.6 | Language keep | English reviews | Retained, not dropped |
| E2.7 | Language filter | Non-allowlist languages | Flagged/excluded per policy |
| E2.8 | Order in pipeline | Scrub runs before embed/LLM/publish | Downstream never sees raw PII |
| E2.9 | No semantic destruction | Compare pre/post meaning on sample | Theme-relevant content preserved |

## Metrics / targets
- PII recall ≥ 0.98 on the synthetic corpus; **leak count = 0** is a hard gate.
- Over-redaction (false positive) rate ≤ 5%.
- Language classification accuracy ≥ 0.95 on labeled set.

## Definition of done
All E2.* pass; PII leak count is 0 across `body_clean` and any rendered text in later phases.
