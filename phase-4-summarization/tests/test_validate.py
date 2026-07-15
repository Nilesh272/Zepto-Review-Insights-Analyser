"""E4.1/E4.2/E4.3 + X4.1/X4.2/X4.3/X4.6/X4.13 — quote grounding hard gate."""

from datetime import datetime, timezone

from pulse.config import Settings
from pulse.models import CleanReview, QuoteCandidate, ThemeDraft
from pulse.reasoning.validate import validate_quotes


def _review(review_id: str, body: str, rating: int = 2) -> CleanReview:
    return CleanReview(
        source="app_store", product_id="groww", review_id=review_id, rating=rating,
        body=body, locale="in", posted_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        body_clean=body, lang="en",
    )


CORPUS = [
    _review("r1", "The app freezes exactly when the market opens, very frustrating."),
    _review("r2", "Support takes days to reply and doesn't solve the issue."),
    _review("r3", "Good for beginners but lacks detailed analysis tools."),
]


def _draft(*quotes: QuoteCandidate) -> ThemeDraft:
    return ThemeDraft(cluster_id=0, title="T", summary="s", candidate_quotes=list(quotes))


def test_verbatim_quote_validated_with_provenance():
    draft = _draft(QuoteCandidate(text="The app freezes exactly when the market opens, very frustrating.", review_id="r1"))
    themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert stats["validated_quotes"] == 1 and stats["dropped_quotes"] == 0
    q = themes[0].quotes[0]
    assert q.validated is True and q.review_id == "r1"


def test_fabricated_quote_dropped():
    # X4.1 — never appears in any review.
    draft = _draft(QuoteCandidate(text="This app is the best trading platform ever made.", review_id="r1"))
    themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert stats["dropped_quotes"] == 1 and themes[0].quotes == []


def test_whitespace_and_case_accepted():
    # E4.3 — normalization-only differences are fine.
    draft = _draft(QuoteCandidate(text="  support TAKES days to reply   and doesn't solve the issue. ", review_id="r2"))
    _themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert stats["validated_quotes"] == 1


def test_paraphrase_rejected():
    # X4.2 — semantically similar but not verbatim.
    draft = _draft(QuoteCandidate(text="Support is slow to respond and never fixes anything.", review_id="r2"))
    _themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert stats["dropped_quotes"] == 1


def test_stitched_across_reviews_rejected():
    # X4.3 — a quote spanning two different reviews has no single-source provenance.
    draft = _draft(QuoteCandidate(text="The app freezes exactly when the market opens Support takes days to reply", review_id="r1"))
    _themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert stats["dropped_quotes"] == 1


def test_provenance_corrected_when_unique_match():
    # Claims the wrong id, but the text is verbatim in exactly one review -> accept & correct.
    draft = _draft(QuoteCandidate(text="Good for beginners but lacks detailed analysis tools.", review_id="r1"))
    themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert stats["validated_quotes"] == 1
    assert themes[0].quotes[0].review_id == "r3"


def test_theme_kept_without_quotes_when_all_fail():
    # X4.6 — keep the theme + summary, just no quotes.
    draft = _draft(QuoteCandidate(text="totally made up", review_id="r1"))
    themes, stats = validate_quotes([draft], CORPUS, Settings())
    assert len(themes) == 1 and themes[0].quotes == []
    assert stats["themes_without_quotes"] == 1


def test_offensive_quote_dropped_when_enabled():
    # X4.13 — grounded but filtered by policy.
    corpus = CORPUS + [_review("r4", "this app is a scam and useless garbage")]
    draft = _draft(QuoteCandidate(text="this app is a scam and useless garbage", review_id="r4"))
    settings = Settings(summarize={"drop_offensive_quotes": True})
    themes, stats = validate_quotes([draft], corpus, settings)
    assert stats["offensive_dropped"] == 1 and themes[0].quotes == []
