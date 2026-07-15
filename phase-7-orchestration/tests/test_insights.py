"""Insight lens extraction — reviews mapped to product-research questions."""

from datetime import datetime, timezone

from pulse.config import InsightLens, InsightsConfig, Settings
from pulse.models import CleanReview
from pulse.reasoning.insights import extract_insights, _score_text
from pulse.reasoning.validate import validate_quotes


def _review(rid, body, rating=2):
    return CleanReview(
        source="app_store", product_id="spotify", review_id=rid, rating=rating,
        body=body, body_clean=body, locale="us",
        posted_at=datetime(2026, 6, 1, tzinfo=timezone.utc), lang="en", pii_spans=[],
    )


def test_score_text_phrase_weighting():
    assert _score_text("hard to find new artists on spotify", ["hard to find", "new artist"]) >= 5


def test_extract_insights_maps_questions():
    reviews = [
        _review("r1", "I can't find new music — search is terrible and discover is broken", 2),
        _review("r2", "Hard to find underground artists unless I already know them", 1),
        _review("r3", "Discover weekly keeps playing the same songs over and over", 2),
        _review("r4", "Recommendations are wrong and irrelevant for my taste", 1),
        _review("r5", "The algorithm suggests songs I already skipped a hundred times", 2),
        _review("r6", "I use spotify for workouts and gym playlists every day", 5),
        _review("r7", "Perfect for my commute and driving to work", 4),
        _review("r8", "I listen on my phone during runs and gym sessions", 5),
        _review("r9", "I replay the same song on loop because it's comforting", 3),
        _review("r10", "Stuck listening to the same artist over and over again", 2),
        _review("r11", "Free tier has too many ads and limited skips for discovery", 2),
        _review("r12", "Premium subscriber but podcasts recommendations are awful", 2),
        _review("r13", "I wish spotify had better offline download for travel", 2),
        _review("r14", "Missing feature — need better playlist tools", 1),
        _review("r15", "Would love if they improved search, so frustrating", 2),
    ]
    lenses = [
        InsightLens(id="discovery", question="Why do users struggle to discover new music?",
                    keywords=["discover", "find", "new music", "search", "hard to find"]),
        InsightLens(id="recs", question="What are the most common frustrations with recommendations?",
                    keywords=["recommend", "algorithm", "same songs", "wrong"]),
        InsightLens(id="behaviors", question="What listening behaviors are users trying to achieve?",
                    keywords=["workout", "commute", "drive", "gym", "listen"]),
        InsightLens(id="repeat", question="What causes users to repeatedly listen to the same content?",
                    keywords=["same song", "repeat", "loop", "over and over"]),
        InsightLens(id="unmet", question="What unmet needs emerge consistently across reviews?",
                    keywords=["wish", "need", "missing", "frustrating", "would love"]),
    ]
    cfg = InsightsConfig(min_reviews_per_lens=2, max_quotes_per_lens=2)
    drafts = extract_insights(reviews, lenses, cfg)

    questions = {d.title for d in drafts}
    assert "Why do users struggle to discover new music?" in questions
    assert "What are the most common frustrations with recommendations?" in questions
    assert "AI analysis of" in drafts[0].summary or "reviews" in drafts[0].summary.lower()
    assert all(d.candidate_quotes for d in drafts)


def test_insights_quotes_ground_after_validation():
    reviews = [
        _review("r1", "Discover weekly is broken and I can't find new artists", 2),
        _review("r2", "Search never surfaces new music I would enjoy", 1),
        _review("r3", "Browse tab is useless for finding anything fresh", 2),
    ]
    lens = [InsightLens(id="d", question="Why do users struggle to discover new music?",
                        keywords=["discover", "find", "new music", "search", "browse"])]
    drafts = extract_insights(reviews, lens, InsightsConfig(min_reviews_per_lens=2, max_quotes_per_lens=2))
    themes, stats = validate_quotes(drafts, reviews, Settings())
    assert stats["validated_quotes"] >= 1
    assert themes[0].quotes[0].validated is True


def test_balance_matched_interleaves_sentiment():
    from pulse.reasoning.insights import _balance_matched, _pick_balanced_quotes

    reviews = [
        _review("p1", "love fast delivery every day reorder staples", 5),
        _review("p2", "great deals and cashback always order", 5),
        _review("n1", "refund cancelled delay terrible support", 1),
        _review("n2", "missing items and late delivery frustrating", 1),
        _review("m1", "okay service but search is hard to find", 3),
    ]
    matched = [(r, 5 - i) for i, r in enumerate(reviews)]
    bal = _balance_matched(matched, 4)
    ratings = [r.rating for r, _ in bal]
    assert any(x >= 4 for x in ratings)
    assert any(x <= 2 for x in ratings)

    picks = _pick_balanced_quotes(matched, 2, "What prevents users from exploring new categories?")
    pick_ratings = {r.rating for r, _ in picks}
    assert any(x >= 4 for x in pick_ratings)
    assert any(x <= 2 for x in pick_ratings)


def test_extract_insights_includes_positive_quotes_when_present():
    reviews = [
        _review("n1", "cannot explore new categories refund delay missing items support bad", 1),
        _review("n2", "prevented from trying new category because of cancelled order", 1),
        _review("n3", "barriers: out of stock and terrible late delivery again", 2),
        _review("p1", "love exploring new categories cafe and pharmacy always great", 5),
        _review("p2", "easy to discover new products deals and search work perfectly", 5),
        _review("p3", "trying new snacks every week habit and reorder favorites", 4),
    ]
    lens = [
        InsightLens(
            id="prevent",
            question="What prevents users from exploring new categories?",
            keywords=["explore", "new", "category", "prevent", "barrier", "discover", "trying"],
        )
    ]
    cfg = InsightsConfig(
        min_reviews_per_lens=2,
        max_quotes_per_lens=4,
        balance_sentiment=True,
        backend="deterministic",
    )
    drafts = extract_insights(reviews, lens, cfg)
    assert drafts
    by_id = {r.review_id: r for r in reviews}
    quote_ratings = [by_id[q.review_id].rating for q in drafts[0].candidate_quotes]
    assert any(r >= 4 for r in quote_ratings), quote_ratings
    assert any(r <= 2 for r in quote_ratings), quote_ratings
