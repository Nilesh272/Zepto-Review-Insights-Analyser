"""summarize_clusters orchestration (architecture §3.2, §6, §11).

Runs the configured summarizer over the top-ranked clusters, enforcing the per-run budget
(stopping with partial results rather than overspending), de-duplicating themes, and
re-scrubbing PII out of generated text before anything heads to grounding/render.
"""

from __future__ import annotations

import logging

from pulse.models import ThemeDraft
from pulse.reasoning.llm import build_summarizer
from pulse.reasoning.select import select_balanced_clusters

logger = logging.getLogger("pulse.reasoning.summarize")


def _norm_title(title: str) -> str:
    return " ".join(title.lower().split())


def _merge(into: ThemeDraft, other: ThemeDraft) -> None:
    """Merge a duplicate-title draft into an existing one (X4.11)."""
    seen = {(q.text, q.review_id) for q in into.candidate_quotes}
    for q in other.candidate_quotes:
        if (q.text, q.review_id) not in seen:
            into.candidate_quotes.append(q)
            seen.add((q.text, q.review_id))
    for a in other.actions:
        if a not in into.actions:
            into.actions.append(a)
    for w in other.who_this_helps:
        if w not in into.who_this_helps:
            into.who_this_helps.append(w)
    into.supporting_review_ids = sorted(set(into.supporting_review_ids) | set(other.supporting_review_ids))


def _rescrub(draft: ThemeDraft, scrubber) -> None:
    """Re-scrub PII from generated fields before publish (X4.12)."""
    draft.title = scrubber.scrub(draft.title).body_clean
    draft.summary = scrubber.scrub(draft.summary).body_clean
    draft.actions = [scrubber.scrub(a).body_clean for a in draft.actions]


def summarize_clusters(clusters, clean_reviews, settings, budget) -> list[ThemeDraft]:
    """Summarize the top-N clusters into de-duplicated ThemeDrafts (best-first order)."""
    cfg = settings.summarize
    top_n = settings.top_themes.max
    by_id = {r.review_id: r for r in clean_reviews}
    summarizer = build_summarizer(settings)

    scrubber = None
    if cfg.rescrub_output:
        from pulse.preprocess.pii import Scrubber

        scrubber = Scrubber(redact_names=settings.preprocess.redact_names)

    drafts: list[ThemeDraft] = []
    by_title: dict[str, ThemeDraft] = {}
    halted = False

    selected = select_balanced_clusters(
        clusters,
        top_n,
        min_critical=cfg.min_critical_themes,
        critical_max_rating=cfg.critical_max_rating,
    )

    for cluster in selected:
        if cluster.size < cfg.min_cluster_size_for_theme:
            continue
        reviews = [by_id[rid] for rid in cluster.review_ids if rid in by_id]
        if not reviews:
            continue

        # Estimate cost first so we can stop *before* breaching the cap (E4.8 / X4.9).
        est_tokens = max(1, sum(len(r.body_clean) for r in reviews) // 4)
        est_cost = est_tokens / 1000 * cfg.cost_per_1k_tokens
        if budget.would_exceed(tokens=est_tokens, cost_usd=est_cost):
            logger.warning("budget would be exceeded — halting summarization with partial themes")
            halted = True
            break

        draft, used = summarizer.summarize_cluster(cluster, reviews, cfg)
        budget.add(tokens=used, cost_usd=used / 1000 * cfg.cost_per_1k_tokens)

        if scrubber is not None:
            _rescrub(draft, scrubber)

        key = _norm_title(draft.title)
        if key in by_title:
            _merge(by_title[key], draft)  # X4.11 duplicate themes
        else:
            by_title[key] = draft
            drafts.append(draft)

    if not drafts:
        logger.info("no themes produced — low-signal run")
    return drafts, halted
