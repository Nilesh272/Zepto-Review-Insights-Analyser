"""Phase 1 quality filters.

Per the requested rules, a review is dropped when it:
  - contains any emoji              (filters.drop_emoji)
  - has fewer than `min_words`      (filters.min_words)
  - is detected as a language not in `language_allowlist` (filters.drop_other_languages)

Language detection is pluggable (a `Detector` callable) so tests are deterministic and the
heavy `langdetect` dependency is isolated. The default detector seeds langdetect for
reproducibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from pulse.config import Settings
from pulse.utils.text import has_emoji, word_count

logger = logging.getLogger("pulse.ingestion.filters")

# Returns an ISO language code, or None if undetermined.
Detector = Callable[[str], "str | None"]


@dataclass
class Classification:
    reason: str | None  # None => keep
    lang: str | None
    word_count: int


def default_detector() -> Detector:
    """Deterministic language detector (delegates to the canonical preprocess.language module)."""
    from pulse.preprocess.language import default_detector as _canonical

    return _canonical()


def classify(text: str, settings: Settings, detector: Detector) -> Classification:
    """Classify a review body for the quality filters.

    Deterministic order: emoji -> min_words -> language. The first matching rule wins so the
    recorded reason is unambiguous. Language is detected at most once and returned for kept
    reviews. Inconclusive detection keeps the review (avoids dropping valid text on uncertainty).
    """
    filters = settings.filters
    wc = word_count(text)

    if filters.drop_emoji and has_emoji(text):
        return Classification(reason="emoji", lang=None, word_count=wc)

    if wc < filters.min_words:
        return Classification(reason="too_short", lang=None, word_count=wc)

    lang = detector(text) if text.strip() else None
    if filters.drop_other_languages and lang is not None and lang not in settings.language_allowlist:
        return Classification(reason=f"language:{lang}", lang=lang, word_count=wc)

    return Classification(reason=None, lang=lang, word_count=wc)


def drop_reason(text: str, settings: Settings, detector: Detector) -> str | None:
    """Convenience wrapper returning just the drop reason (or None to keep)."""
    return classify(text, settings, detector).reason
