"""Language detection + allowlist filtering (architecture §11; plan Phase 2).

This is the canonical language module. The ingestion quality filter (Phase 1) reuses
`default_detector` from here so detection behaves identically across phases. langdetect is
seeded for deterministic results.
"""

from __future__ import annotations

from typing import Callable

# Returns an ISO language code, or None if undetermined.
Detector = Callable[[str], "str | None"]


def detect_language(text: str | None) -> str | None:
    """Detect the dominant language of `text`, or None when undetermined/too short."""
    if not text or not text.strip():
        return None
    from langdetect import DetectorFactory, LangDetectException
    from langdetect import detect as _detect

    DetectorFactory.seed = 0
    try:
        return _detect(text)
    except LangDetectException:
        return None


def default_detector() -> Detector:
    """Return the deterministic language detector callable."""
    return detect_language


def is_allowed(text: str | None, allowlist: list[str]) -> bool:
    """True if the text is in an allowlisted language (or detection is inconclusive).

    Inconclusive detection returns True to avoid dropping valid (often short) reviews.
    """
    lang = detect_language(text)
    return lang is None or lang in allowlist
