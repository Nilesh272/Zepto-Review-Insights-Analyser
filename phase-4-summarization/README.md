# Phase 4 — Summarization & Grounding

Self-contained snapshot of the agent through **Phase 4** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes Phases 0–3). The
`summarize_clusters` and `validate_quotes` skill tools are now **real**: the agent turns the
top-ranked clusters into named themes (with candidate quotes, actions, "who this helps") and
then enforces a **hard grounding gate** so every published quote appears verbatim in real
review text.

## What's new vs Phase 3

| Area | Module | Architecture ref |
|---|---|---|
| Summarizer backends (deterministic + LLM) | `pulse/reasoning/llm.py` | §3.2, §6 |
| `summarize_clusters` orchestration (budget/dedupe/re-scrub) | `pulse/reasoning/summarize.py` | §6, §11 |
| `validate_quotes` grounding gate | `pulse/reasoning/validate.py` | §6, §11 |
| Real `summarize_clusters` + `validate_quotes` tools | `pulse/agent/tools.py` | §3.2 |
| `ThemeDraft` / `QuoteCandidate` contracts | `pulse/models.py` | §5 |
| Budget `would_exceed` (stop before overspending) | `pulse/agent/budget.py` | §11 |

## Pipeline

`summarize_clusters` runs on the ranked `Cluster[]` + `CleanReview[]`:

1. For each of the top-N clusters (size ≥ `min_cluster_size_for_theme`), the summarizer drafts
   a theme: title, summary, candidate quotes (with cited `review_id`), actions, audience.
2. The per-run **budget is checked before each cluster** — if the next cluster would breach the
   token/cost cap, summarization stops and keeps the partial themes (no overspend).
3. Generated text is **re-scrubbed for PII**, and **duplicate themes are merged** by title.

`validate_quotes` is the hard gate:

- A quote is published only if it appears **verbatim** (whitespace/case-normalized) in a single
  real review body. Paraphrases and quotes stitched across reviews are rejected.
- Provenance is verified against the cited `review_id` (corrected if the text uniquely matches
  another review). A theme whose quotes all fail is kept with its summary but no quotes.

### Backends (swappable, no code changes)

`summarize.backend`:
- `deterministic` *(default)* — offline, reproducible, **extractive**. Only ever copies real
  review substrings, so it cannot fabricate quotes and cannot be steered by instructions
  embedded in review text (injection-proof by construction). Used by the test suite.
- `openai` — generative chat model (optional `llm` extra; lazy import). Review text is wrapped
  in an explicit **untrusted-data** block and the system prompt forbids following any
  instructions inside it; the JSON response is parsed with a repair pass.

Tuning lives in `config/settings.yaml` under `summarize`.

## Safety properties (architecture §11)

- **Grounding:** zero hallucinated quotes — unverifiable quotes are dropped, not published.
- **Prompt injection:** reviews are treated as data; the deterministic backend never executes
  them, and the LLM backend fences + forbids embedded instructions.
- **PII:** generated theme text is re-scrubbed before grounding/render.
- **Cost control:** token/cost caps are enforced *before* each cluster is summarized.

## Setup / test

```bash
cd phase-4-summarization
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # deterministic backend needs no API key
python -m pytest                         # synthetic + fixtures; no network required
```

The optional generative backend needs `pip install '.[llm]'` and an `OPENAI_API_KEY`; it is
**not** exercised by tests (which run fully offline and deterministically).

## Notes
- Determinism: the deterministic summarizer is purely extractive and order-stable; grounding is
  exact substring matching after whitespace/case normalization.
- Quality is checked against a labeled synthetic corpus (`tests/synth.py`): theme titles map to
  the right gold themes, actions/audience are present, and 100% of published quotes are grounded.
- Edge cases covered: fabricated/paraphrased/stitched quotes, prompt injection, budget halt with
  partial themes, malformed LLM JSON, duplicate-theme merge, low-signal runs, offensive-quote
  policy filter (see `tests/`).
