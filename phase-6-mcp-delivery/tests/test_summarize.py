"""E4.4/E4.5/E4.6 + X4.7/X4.11 — deterministic summarization quality and dedupe."""

from pulse.agent.budget import Budget
from pulse.config import Settings
from pulse.reasoning.summarize import summarize_clusters
from tests.synth import build_gold_clusters, build_themed_reviews


def _budget():
    return Budget(max_tokens=1_000_000, max_cost_usd=100.0)


def test_produces_one_theme_per_cluster():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    drafts, halted = summarize_clusters(clusters, reviews, Settings(), _budget())
    assert not halted
    assert len(drafts) == 3


def test_theme_quality_titles_actions_audience():
    # E4.4 titles on-topic, E4.5 actions present, E4.6 audience framing present.
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    drafts, _ = summarize_clusters(clusters, reviews, Settings(), _budget())

    titles = [d.title.lower() for d in drafts]

    def _any(words):
        return any(any(w in t for w in words) for t in titles)

    # Each gold theme should surface via one of its salient keywords in some title.
    assert _any({"customer", "support", "ticket", "issue"})       # support theme
    assert _any({"crashes", "freezes", "trading", "orders", "lags"})  # performance theme
    assert _any({"navigation", "analytics", "interface", "charts", "reporting"})  # ux theme

    for d in drafts:
        assert d.actions, "every theme should propose actions"
        assert d.who_this_helps, "every theme should map to an audience"
    audiences = {a for d in drafts for a in d.who_this_helps}
    assert audiences & {"Product", "Support", "Leadership"}


def test_candidate_quotes_are_substrings_of_real_reviews():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    drafts, _ = summarize_clusters(clusters, reviews, Settings(), _budget())
    bodies = {r.review_id: r.body_clean for r in reviews}
    for d in drafts:
        for q in d.candidate_quotes:
            assert q.text in bodies[q.review_id]  # extractive => verbatim & grounded


def test_low_signal_when_no_clusters():
    # X4.7 — nothing to summarize.
    drafts, halted = summarize_clusters([], [], Settings(), _budget())
    assert drafts == [] and not halted


def test_small_clusters_skipped():
    reviews, gold = build_themed_reviews(repeats=3)
    clusters = build_gold_clusters(reviews, gold)
    for c in clusters:
        c.size = 1  # below min_cluster_size_for_theme
    drafts, _ = summarize_clusters(clusters, reviews, Settings(), _budget())
    assert drafts == []
