# Phase 3 — Clustering (`cluster_reviews`) — Evaluations

> Verifies embeddings, UMAP + HDBSCAN clustering, and ranking from
> [`implementationPlan.md`](../implementationPlan.md) Phase 3.

## Scope under test
`reasoning/embed.py`, `reasoning/cluster.py`, the `cluster_reviews` tool.

## Test types
- **Unit:** embedding cache/batching; ranking formula.
- **Quality:** clustering against a labeled fixture (reviews tagged with gold themes).
- **Determinism:** fixed seeds → stable clusters.

## Evaluation cases

| ID | What it checks | Method | Pass criteria |
|---|---|---|---|
| E3.1 | Embedding cache | Embed same text twice | 2nd call served from cache; identical vectors |
| E3.2 | Batching | Large input set | Correct batch sizing; no dropped items |
| E3.3 | Cluster coherence | UMAP+HDBSCAN on labeled fixture | Intra-cluster similarity high; clusters align to gold themes |
| E3.4 | Noise handling | Fixture with outliers | Outliers labeled noise, excluded from themes |
| E3.5 | Ranking | Clusters of varied size/recency/rating | Rank = size×recency×rating-spread; expected top theme first |
| E3.6 | Top-N selection | Request top 3–5 | Correct count; stable order |
| E3.7 | Determinism | Re-run with fixed seed | Identical cluster assignments + order |
| E3.8 | Single-cluster case | Homogeneous input | Returns 1 cluster, no crash |

## Metrics / targets
- Clustering quality vs gold labels: Adjusted Rand Index ≥ 0.6 (tune on fixtures).
- Top-1 theme match rate ≥ 0.8 on fixture set.
- Determinism: identical assignments across 3 reruns with same seed.

## Definition of done
All E3.* pass; clustering is reproducible; noise/edge distributions handled (see edge-case
file).
