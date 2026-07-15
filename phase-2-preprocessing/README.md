# Phase 2 — Preprocessing & Safety

Self-contained snapshot of the agent through **Phase 2** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes Phases 0–1). The
`scrub_pii` skill tool is now **real**: it removes PII before any downstream step and emits
`CleanReview[]` with an audit of what was redacted.

## What's new vs Phase 1

| Area | Module | Architecture ref |
|---|---|---|
| PII scrubbing (email/phone/card/account/name) | `pulse/preprocess/pii.py` | §11 |
| Language detection + allowlist (canonical) | `pulse/preprocess/language.py` | §11 |
| Real `scrub_pii` tool (NormalizedReview → CleanReview) | `pulse/agent/tools.py` | §3.2 |
| Ingestion reuses the canonical detector | `pulse/ingestion/filters.py` | — |

## PII scrubbing

`scrub_pii` runs **after** ingestion and **before** clustering/LLM/publish (architecture §11).
For each review it:
- NFKC-normalizes the text (defeats fullwidth/homoglyph evasion),
- redacts emails (incl. obfuscations like `name [at] domain dot com`), phone numbers, card-
  and account-like numbers, and person names (the review's own author + cue-based mentions),
- writes `body_clean`, a scrubbed `title`, and `pii_spans` (offsets + label) for audit.

Detection runs in priority order with no overlapping claims, so offsets stay consistent and
the first matching rule wins. Version numbers and years are intentionally **not** matched.

Tuning lives in `config/settings.yaml` under `preprocess` (`redact_names`, `scrub_title`,
`redetect_language`).

## Setup / test

```bash
cd phase-2-preprocessing
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest          # fixtures-based; no network required
```

## Notes
- Language filtering still happens at **ingestion** (Phase 1, per request); Phase 2 keeps the
  canonical detector here and the ingestion filter delegates to it (no duplicate logic).
- Name redaction is heuristic (author name + cues) and deliberately conservative to avoid
  over-redacting product/feature words.
