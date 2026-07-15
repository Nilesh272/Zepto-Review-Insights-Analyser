"""Reasoning layer (architecture §6).

Phase 3 implements clustering (`cluster_reviews`): embeddings -> UMAP -> HDBSCAN -> ranking.
The LLM summarization (`summarize_clusters`) and quote grounding (`validate_quotes`) arrive in
Phase 4.
"""
