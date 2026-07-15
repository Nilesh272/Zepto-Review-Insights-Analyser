"""Text helpers for ingestion quality filtering and near-duplicate detection.

Used by Phase 1 normalization (architecture §3.2). Pure functions, no I/O, deterministic.
"""

from __future__ import annotations

import hashlib
import re

# Common emoji / pictograph blocks. Intentionally excludes plain ASCII punctuation and
# arrows that overlap with ordinary text symbols.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs (incl. supplemental + extended-A)
    "\U0001F000-\U0001F0FF"  # mahjong / dominoes / playing cards
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U00002600-\U000027BF"  # misc symbols + dingbats (incl. heart, sun, etc.)
    "\U00002B00-\U00002BFF"  # misc symbols & arrows (stars, etc.)
    "\U0000FE00-\U0000FE0F"  # variation selectors
    "\U00002190-\U000021FF"  # arrows used as emoji bases (kept narrow)
    "\U00002300-\U000023FF"  # technical (hourglass, keyboard, etc.)
    "]",
    flags=re.UNICODE,
)

_WORD_PATTERN = re.compile(r"\b\w+\b", flags=re.UNICODE)
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def has_emoji(text: str | None) -> bool:
    """True if the text contains at least one emoji/pictograph character."""
    if not text:
        return False
    return _EMOJI_PATTERN.search(text) is not None


def strip_emoji(text: str | None) -> str:
    """Remove emoji characters (offered for an alternative 'strip' policy)."""
    if not text:
        return ""
    return _EMOJI_PATTERN.sub("", text)


def word_count(text: str | None) -> int:
    """Count word-like tokens (unicode-aware)."""
    if not text:
        return 0
    return len(_WORD_PATTERN.findall(text))


def normalize_for_hash(text: str | None) -> str:
    """Lowercase, drop non-alphanumerics, collapse whitespace — for near-dup matching."""
    if not text:
        return ""
    lowered = text.lower()
    collapsed = _NON_ALNUM.sub(" ", lowered)
    return " ".join(collapsed.split())


def text_fingerprint(text: str | None) -> str:
    """Stable fingerprint of normalized text for near-duplicate detection."""
    return hashlib.sha1(normalize_for_hash(text).encode("utf-8")).hexdigest()
