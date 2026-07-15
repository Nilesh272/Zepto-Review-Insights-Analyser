"""Google Docs `batchUpdate` request building (architecture §3.2, §8.1).

Builds the requests for a new dated, anchored section appended to a product's running Doc.
Requests are produced top-to-bottom with a running insertion index, so the heading (and its
named-range anchor) are established before the body (X5.11). Quotes are inserted verbatim —
only summaries/titles are length-capped, never quote text (E5.8 / X5.12).

`validate_docs_requests` encodes the (faked) Docs `batchUpdate` request contract used by tests
(E5.1); no live Docs API is touched in this phase.
"""

from __future__ import annotations

import re

from pulse.utils.isoweek import parse_iso_week

_HEADING_1 = "HEADING_1"
_HEADING_2 = "HEADING_2"
_NORMAL = "NORMAL_TEXT"
_BULLET_PRESET = "BULLET_DISC_CIRCLE_SQUARE"


def slugify(value: str) -> str:
    """Lowercase, hyphenate; keep only [a-z0-9-] (X5.6 product names with spaces/punct)."""
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "product"


def section_anchor(product_id: str, iso_week: str) -> str:
    """Deterministic, collision-free anchor: ``pulse-<product>-<year>-W<ww>`` (E5.3 / X5.7)."""
    iso = parse_iso_week(iso_week)
    return f"pulse-{slugify(product_id)}-{iso.year}-W{iso.week:02d}"


def _truncate(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


class DocsRequestBuilder:
    """Accumulates Docs requests while tracking the running insertion index."""

    def __init__(self, start_index: int = 1):
        self.index = start_index
        self.requests: list[dict] = []

    def _insert(self, text: str) -> tuple[int, int]:
        start = self.index
        self.requests.append({"insertText": {"location": {"index": start}, "text": text}})
        self.index += len(text)
        return start, self.index

    def _paragraph_style(self, start: int, end: int, style: str) -> None:
        self.requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {"namedStyleType": style},
                    "fields": "namedStyleType",
                }
            }
        )

    def heading(self, text: str, *, level: int, anchor: str | None = None) -> None:
        start, end = self._insert(text + "\n")
        self._paragraph_style(start, end, _HEADING_1 if level == 1 else _HEADING_2)
        if anchor:
            # Named range spans the heading text only (exclude the trailing newline).
            self.requests.append(
                {"createNamedRange": {"name": anchor, "range": {"startIndex": start, "endIndex": end - 1}}}
            )

    def paragraph(self, text: str) -> None:
        start, end = self._insert(text + "\n")
        self._paragraph_style(start, end, _NORMAL)

    def bullets(self, items: list[str], *, italic: bool = False) -> None:
        if not items:
            return
        block_start = self.index
        for item in items:
            self._insert(item + "\n")
        block_end = self.index
        self.requests.append(
            {
                "createParagraphBullets": {
                    "range": {"startIndex": block_start, "endIndex": block_end},
                    "bulletPreset": _BULLET_PRESET,
                }
            }
        )
        if italic:
            self.requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": block_start, "endIndex": block_end},
                        "textStyle": {"italic": True},
                        "fields": "italic",
                    }
                }
            )


def build_docs_requests(
    themes,
    *,
    product_name: str,
    iso_week: str,
    anchor: str,
    cfg,
    low_signal: bool = False,
    start_index: int = 1,
) -> list[dict]:
    """Build the ordered `batchUpdate` requests for the week's section."""
    b = DocsRequestBuilder(start_index=start_index)
    b.heading(f"{product_name} — Weekly Review Pulse — {iso_week}", level=1, anchor=anchor)

    if low_signal or not themes:
        b.paragraph(
            "Low-signal week: too few reviews to extract reliable themes. "
            "No themes are reported for this period."
        )
        return b.requests

    for theme in themes:
        b.heading(_truncate(theme.title, cfg.max_title_chars), level=2)
        if theme.summary:
            b.paragraph(_truncate(theme.summary, cfg.max_summary_chars))

        quotes = [q.text for q in theme.quotes[: cfg.max_quotes_per_theme]]
        if quotes:
            b.paragraph("Representative quotes:")
            b.bullets([f"\u201c{q}\u201d" for q in quotes], italic=True)  # verbatim, no mutation

        if theme.actions:
            b.paragraph("Action ideas:")
            b.bullets(list(theme.actions))

        if theme.who_this_helps:
            b.paragraph("Who this helps: " + ", ".join(theme.who_this_helps))

    return b.requests


_REQUIRED = {
    "insertText": lambda r: isinstance(r.get("text"), str)
    and r["text"] != ""
    and _valid_index(r.get("location", {}).get("index")),
    "updateParagraphStyle": lambda r: _valid_range(r.get("range"))
    and "namedStyleType" in r.get("paragraphStyle", {}),
    "createNamedRange": lambda r: isinstance(r.get("name"), str)
    and r["name"] != ""
    and _valid_range(r.get("range")),
    "createParagraphBullets": lambda r: _valid_range(r.get("range")) and "bulletPreset" in r,
    "updateTextStyle": lambda r: _valid_range(r.get("range")) and "textStyle" in r,
}


def _valid_index(v) -> bool:
    return isinstance(v, int) and v >= 1


def _valid_range(rng) -> bool:
    return (
        isinstance(rng, dict)
        and _valid_index(rng.get("startIndex"))
        and _valid_index(rng.get("endIndex"))
        and rng["endIndex"] > rng["startIndex"]
    )


def validate_docs_requests(requests: list[dict]) -> None:
    """Validate requests against the (faked) Docs batchUpdate contract (E5.1).

    Raises ValueError on the first invalid request.
    """
    if not isinstance(requests, list) or not requests:
        raise ValueError("docs requests must be a non-empty list")
    for i, req in enumerate(requests):
        if not isinstance(req, dict) or len(req) != 1:
            raise ValueError(f"request {i} must be a single-keyed object, got {req!r}")
        (kind, body), = req.items()
        if kind not in _REQUIRED:
            raise ValueError(f"request {i}: unknown request type {kind!r}")
        if not _REQUIRED[kind](body):
            raise ValueError(f"request {i}: invalid {kind} payload: {body!r}")
