"""E4.8 / X4.9 — summarization halts within budget and keeps partial results."""

from pulse.agent.budget import Budget
from pulse.config import Settings
from pulse.reasoning.summarize import summarize_clusters
from tests.synth import build_gold_clusters, build_themed_reviews


def test_halts_with_partial_themes_within_cap():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)  # 3 clusters

    # Enough budget for ~one cluster's worth of tokens, not all three.
    one_cluster_tokens = max(
        1, sum(len(r.body_clean) for r in reviews if r.review_id in clusters[0].review_ids) // 4
    )
    budget = Budget(max_tokens=one_cluster_tokens + 5, max_cost_usd=100.0)

    drafts, halted = summarize_clusters(clusters, reviews, Settings(), budget)
    assert halted is True
    assert 0 < len(drafts) < 3
    assert budget.tokens <= budget.max_tokens  # never overspent


def test_no_halt_with_ample_budget():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    drafts, halted = summarize_clusters(clusters, reviews, Settings(), Budget(10**7, 100.0))
    assert halted is False and len(drafts) == 3
