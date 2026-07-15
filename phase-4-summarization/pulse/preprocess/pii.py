"""PII scrubbing (architecture §11).

Redacts emails (incl. common obfuscations), phone numbers, card- and account-like numbers,
and person names (the review's own author plus cue-based mentions) before any text reaches
embeddings, the LLM, or published output.

Text is NFKC-normalized first (defeats fullwidth/homoglyph evasion); reported `pii_spans`
offsets are relative to that normalized text, which is also what `body_clean` is derived from.
Detection runs in priority order and never double-claims overlapping characters, so the first
matching rule wins and offsets stay consistent.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pulse.models import Span

# --- patterns -----------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Obfuscated: "name [at] domain dot com", "name (at) domain dot com", "name at domain dot com"
_EMAIL_OBFUS_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+\s*(?:\[at\]|\(at\)|\s+at\s+)\s*"
    r"[A-Za-z0-9.\-]+\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*[A-Za-z]{2,}",
    re.IGNORECASE,
)
# Account/card with explicit keyword takes priority over the generic numeric rule.
_ACCOUNT_RE = re.compile(
    r"(?:account(?:\s*(?:no\.?|number|#))?|a/c|acct\.?)[:\s.#-]*(\d{6,18})",
    re.IGNORECASE,
)
# A run of digits with phone/card-style separators (>= 9 chars long to skip years/versions).
_NUMERIC_RE = re.compile(r"\+?\d[\d\s\-().]{7,}\d")
# Name cues; the captured token must be Capitalized and not a common word.
_NAME_CUE_RE = re.compile(
    r"(?:my name is|name is|i am|i'?m|regards,?|sincerely,?)\s+"
    r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)",
    re.IGNORECASE,
)
_COMMON_CAPS = {
    "I", "The", "This", "That", "Great", "Good", "Bad", "Nice", "Best", "Worst",
    "App", "Application", "Very", "So", "Really", "Not", "Frustrated", "Happy",
}


@dataclass
class ScrubResult:
    body_clean: str
    spans: list[Span] = field(default_factory=list)
    normalized: str = ""

    def label_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.spans:
            counts[s.label] = counts.get(s.label, 0) + 1
        return counts


class Scrubber:
    def __init__(self, *, redact_names: bool = True):
        self.redact_names = redact_names

    # -- detection -------------------------------------------------------------

    def detect(self, text: str, *, author: str | None = None) -> list[Span]:
        """Return non-overlapping PII spans (offsets into the NFKC-normalized text)."""
        claimed: list[tuple[int, int]] = []
        spans: list[Span] = []

        def overlaps(s: int, e: int) -> bool:
            return any(not (e <= cs or s >= ce) for cs, ce in claimed)

        def add(s: int, e: int, label: str) -> None:
            if s < e and not overlaps(s, e):
                claimed.append((s, e))
                spans.append(Span(start=s, end=e, label=label))

        for m in _EMAIL_RE.finditer(text):
            add(m.start(), m.end(), "EMAIL")
        for m in _EMAIL_OBFUS_RE.finditer(text):
            add(m.start(), m.end(), "EMAIL")

        # Keyword account/card before the generic numeric rule.
        for m in _ACCOUNT_RE.finditer(text):
            add(m.start(1), m.end(1), "ACCOUNT")

        for m in _NUMERIC_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            n = len(digits)
            if 13 <= n <= 19:
                add(m.start(), m.end(), "CARD")
            elif 10 <= n <= 12:
                add(m.start(), m.end(), "PHONE")

        if self.redact_names:
            for s, e in self._author_name_spans(text, author):
                add(s, e, "NAME")
            for m in _NAME_CUE_RE.finditer(text):
                name = m.group(1)
                first = name.split()[0]
                if first[:1].isupper() and first not in _COMMON_CAPS:
                    add(m.start(1), m.end(1), "NAME")

        spans.sort(key=lambda sp: sp.start)
        return spans

    @staticmethod
    def _author_name_spans(text: str, author: str | None) -> list[tuple[int, int]]:
        if not author:
            return []
        out: list[tuple[int, int]] = []
        for tok in {t for t in re.split(r"\s+", author) if len(t) >= 3}:
            for m in re.finditer(rf"\b{re.escape(tok)}\b", text, flags=re.IGNORECASE):
                out.append((m.start(), m.end()))
        return out

    # -- scrubbing -------------------------------------------------------------

    def scrub(self, text: str | None, *, author: str | None = None) -> ScrubResult:
        normalized = unicodedata.normalize("NFKC", text or "")
        spans = self.detect(normalized, author=author)

        out: list[str] = []
        prev = 0
        for sp in spans:
            out.append(normalized[prev:sp.start])
            out.append(f"[{sp.label}]")
            prev = sp.end
        out.append(normalized[prev:])

        return ScrubResult(body_clean="".join(out), spans=spans, normalized=normalized)

    def has_pii(self, text: str | None) -> bool:
        return bool(self.detect(unicodedata.normalize("NFKC", text or "")))
