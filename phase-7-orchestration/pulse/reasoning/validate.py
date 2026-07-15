"""validate_quotes — the grounding hard gate (architecture §3.2, §6, §11).

A candidate quote is published only if it appears **verbatim** in a single real review body,
allowing whitespace/case normalization only (not paraphrase). This enforces "quotes must
appear in real review text" and gives every published quote single-source provenance.

Policy:
  - Match against the claimed `review_id` first; if that fails, fall back to the corpus and
    accept only when exactly one review contains the quote (single-source).
  - Paraphrases (X4.2) and quotes stitched across reviews (X4.3) match nothing → dropped.
  - Fabricated quotes (X4.1) match nothing → dropped.
  - A theme whose every quote fails is kept with its summary but no quotes (X4.6).
  - Optionally drop offensive quotes from publish even when grounded (X4.13).
"""

from __future__ import annotations

import logging
import re

from pulse.models import Quote, Theme, ThemeDraft
from pulse.reasoning.llm import is_offensive

logger = logging.getLogger("pulse.reasoning.validate")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _find_provenance(quote: str, claimed_id: str, norm_bodies: dict[str, str]) -> str | None:
    """Return the review_id that verbatim-contains `quote`, or None.

    Prefers the claimed review; otherwise accepts only a unique corpus match (single-source).
    """
    nq = _norm(quote)
    if not nq:
        return None
    if claimed_id in norm_bodies and nq in norm_bodies[claimed_id]:
        return claimed_id
    matches = [rid for rid, body in norm_bodies.items() if nq in body]
    if len(matches) == 1:
        return matches[0]
    return None  # no match, or ambiguous (not single-source)


def validate_quotes(theme_drafts: list[ThemeDraft], clean_reviews, settings) -> tuple[list[Theme], dict]:
    """Convert drafts into grounded Themes; return (themes, stats)."""
    cfg = settings.summarize
    norm_bodies = {r.review_id: _norm(r.body_clean) for r in clean_reviews}

    themes: list[Theme] = []
    validated_n = dropped_n = offensive_n = 0

    for draft in theme_drafts:
        quotes: list[Quote] = []
        seen: set[tuple[str, str]] = set()
        for cand in draft.candidate_quotes:
            rid = _find_provenance(cand.text, cand.review_id, norm_bodies)
            if rid is None:
                dropped_n += 1
                logger.info("dropped ungrounded quote: %r", cand.text[:60])
                continue
            if cfg.drop_offensive_quotes and is_offensive(cand.text):
                offensive_n += 1
                continue
            key = (cand.text, rid)
            if key in seen:
                continue
            seen.add(key)
            quotes.append(Quote(text=cand.text, review_id=rid, validated=True))
            validated_n += 1

        themes.append(
            Theme(
                title=draft.title,
                summary=draft.summary,
                quotes=quotes,
                actions=draft.actions,
                who_this_helps=draft.who_this_helps,
                supporting_review_ids=draft.supporting_review_ids,
            )
        )

    stats = {
        "themes": len(themes),
        "validated_quotes": validated_n,
        "dropped_quotes": dropped_n,
        "offensive_dropped": offensive_n,
        "themes_without_quotes": sum(1 for t in themes if not t.quotes),
    }
    return themes, stats
