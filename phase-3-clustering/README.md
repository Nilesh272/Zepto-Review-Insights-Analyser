# Phase 3 — Clustering

Self-contained snapshot of the agent through **Phase 3** of
[`../docs/implementationPlan.md`](../docs/implementationPlan.md) (includes Phases 0–2). The
`cluster_reviews` skill tool is now **real**: it embeds the scrubbed review bodies, groups them
into themes, and ranks the themes. **No generative LLM** is involved at this stage — only an
embedding model. Summarization arrives in Phase 4.

## What's new vs Phase 2

| Area | Module | Architecture ref |
|---|---|---|
| Embeddings (abstracted backend + cache) | `pulse/reasoning/embed.py` | §6 |
| Clustering + ranking (UMAP → HDBSCAN, fallback) | `pulse/reasoning/cluster.py` | §6 |
| Real `cluster_reviews` tool (CleanReview → Cluster[]) | `pulse/agent/tools.py` | §3.2 |
| Reasoning config | `pulse/config.py`, `config/settings.yaml` | §6 |

## Pipeline

`cluster_reviews` runs **after** PII scrubbing on `CleanReview[]`:

1. **Embed** `body_clean` for every review.
2. **Reduce + cluster** the embeddings → cluster labels (HDBSCAN noise is discarded).
3. **Rank** clusters by `size × recency × rating-spread`, assign `cluster_id` best-first, and
   stash the top-N (per `top_themes.max`) for the downstream summarizer.

### Backends (swappable, no code changes)

- **Embedder** (`reasoning.embedder`):
  - `hashing` *(default)* — deterministic feature hashing, numpy-only, offline, no torch.
  - `sentence-transformers` — semantic embeddings (optional extra; pulls in torch).
- **Clusterer** (`reasoning.clusterer`):
  - `umap_hdbscan` — UMAP dimensionality reduction + HDBSCAN density clustering.
  - `fallback` — deterministic cosine-threshold connected components (numpy-only).
  - `auto` *(default)* — uses UMAP+HDBSCAN when installed and the corpus is large enough,
    otherwise the fallback. Keeps the agent runnable and tests reproducible everywhere.

Tuning lives in `config/settings.yaml` under `reasoning`.

## Setup / test

```bash
cd phase-3-clustering
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # installs numpy + umap-learn + hdbscan
python -m pytest                  # synthetic + fixtures; no network required
```

`umap-learn` / `hdbscan` need a C/C++ toolchain to build. The UMAP+HDBSCAN tests
(`tests/test_cluster_real.py`) **skip** automatically if those libs aren't importable; the
deterministic fallback tests always run.

## Notes
- Determinism: the hashing embedder is content-addressed and the fallback clusterer is
  order-stable; UMAP is seeded via `reasoning.random_seed` (single-threaded when seeded).
- Quality is validated with an Adjusted Rand Index check against a labeled synthetic corpus
  (`tests/synth.py`).
- Edge cases handled: too few reviews (low-signal → no clusters), all-noise corpora, and
  single-theme corpora (see `tests/test_cluster_fallback.py`).
