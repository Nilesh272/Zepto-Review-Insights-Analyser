# Phase 3 — Clustering (`cluster_reviews`) — Edge Cases

> Edge cases for [`implementationPlan.md`](../implementationPlan.md) Phase 3.

| ID | Edge case | Expected handling |
|---|---|---|
| X3.1 | Too few reviews for UMAP/HDBSCAN to be meaningful | Skip clustering; fall back to "low-signal" path |
| X3.2 | All points classified as noise by HDBSCAN | Relax params or fall back; never crash on empty clusters |
| X3.3 | Single dominant theme (one big cluster) | Return one cluster; ranking still valid |
| X3.4 | Many tiny clusters (fragmented feedback) | Rank + take top-N; merge thresholds tuned |
| X3.5 | Highly duplicated text inflating a cluster | Upstream dedup mitigates; ranking not gamed by spam |
| X3.6 | Embedding provider timeout / partial batch | Retry failed batches; fail loudly if incomplete |
| X3.7 | Non-determinism from UMAP randomness | Fixed seed; reproducible assignments |
| X3.8 | Mixed-language vectors skewing clusters | Phase 2 filtering reduces; document residual behavior |
| X3.9 | Outlier 1-star rant unrelated to themes | Lands in noise; not forced into a theme |
| X3.10 | Recency-heavy vs volume-heavy clusters | Ranking formula balances size×recency×rating spread |
| X3.11 | Identical embeddings (degenerate distances) | Stable handling; no divide-by-zero in ranking |
| X3.12 | Very large corpus (memory/time) | Batching + dimensionality reduction keep it bounded |
