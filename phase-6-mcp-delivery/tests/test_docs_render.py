"""E5.1/E5.2/E5.4/E5.8 + X5.1/X5.2/X5.3/X5.4/X5.10/X5.11/X5.12 — Docs request building."""

from pulse.config import Settings
from pulse.models import Quote, Theme
from pulse.render.docs import build_docs_requests, section_anchor, validate_docs_requests


def _theme(title, summary, quotes=(), actions=(), who=()):
    return Theme(
        title=title,
        summary=summary,
        quotes=[Quote(text=q, review_id=f"r{i}", validated=True) for i, q in enumerate(quotes)],
        actions=list(actions),
        who_this_helps=list(who),
    )


THEMES = [
    _theme(
        "App performance & bugs",
        "Crashes during trading hours.",
        quotes=["The app freezes exactly when the market opens, very frustrating."],
        actions=["Stabilize peak-time performance"],
        who=["Product", "Leadership"],
    ),
    _theme(
        "Customer support friction",
        "Slow responses; unresolved tickets.",
        quotes=["Support takes days to reply and doesn't solve the issue."],
        actions=["Improve support SLA visibility"],
        who=["Support"],
    ),
]


def _build(themes, low_signal=False, cfg=None, start_index=1):
    cfg = cfg or Settings().render
    anchor = section_anchor("groww", "2026-W26")
    return build_docs_requests(
        themes, product_name="Groww", iso_week="2026-W26", anchor=anchor, cfg=cfg,
        low_signal=low_signal, start_index=start_index,
    )


def test_requests_are_schema_valid():
    validate_docs_requests(_build(THEMES))  # E5.1 — raises if invalid


def test_section_structure_heading_anchor_and_content():
    reqs = _build(THEMES)
    # E5.2 — first content is the dated HEADING_1 carrying the anchor named range.
    assert reqs[0]["insertText"]["text"].startswith("Groww — Weekly Review Pulse — 2026-W26")
    named = [r for r in reqs if "createNamedRange" in r]
    assert len(named) == 1
    assert named[0]["createNamedRange"]["name"] == "pulse-groww-2026-W26"
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    assert "App performance & bugs" in text  # theme title
    assert "Action ideas:" in text and "Who this helps:" in text


def test_quotes_rendered_verbatim():
    # E5.8 / X5.12 — quote text appears exactly, unmutated.
    reqs = _build(THEMES)
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    for theme in THEMES:
        for q in theme.quotes:
            assert q.text in text


def test_indices_are_monotonic_and_heading_precedes_body():
    # X5.11 — text is built top-to-bottom; the heading insert comes before body inserts,
    # and the named range references the already-inserted heading.
    reqs = _build(THEMES)
    inserts = [r["insertText"] for r in reqs if "insertText" in r]
    indices = [r["location"]["index"] for r in inserts]
    assert indices == sorted(indices)
    heading_end = inserts[0]["location"]["index"] + len(inserts[0]["text"])
    named = next(r for r in reqs if "createNamedRange" in r)
    assert named["createNamedRange"]["range"]["endIndex"] <= heading_end


def test_low_signal_still_dated_and_anchored():
    # X5.1 — zero themes: clear low-signal section, still heading + anchor.
    reqs = _build([], low_signal=True)
    validate_docs_requests(reqs)
    assert any("createNamedRange" in r for r in reqs)
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    assert "Low-signal" in text


def test_theme_without_quotes_has_no_quote_block():
    # X5.2 — summary + actions, but no "Representative quotes:" block.
    theme = _theme("UX gaps", "Confusing navigation.", quotes=(), actions=["Improve nav"], who=["Product"])
    reqs = _build([theme])
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    assert "Representative quotes:" not in text
    assert "Action ideas:" in text


def test_long_summary_truncated_quote_not():
    # X5.3 — summary capped; quote stays verbatim.
    long_summary = "word " * 200
    quote = "this exact quote must survive intact even though the summary is very long indeed"
    theme = _theme("Perf", long_summary, quotes=[quote], actions=["fix"], who=["Product"])
    cfg = Settings().render
    reqs = _build([theme], cfg=cfg)
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    assert quote in text  # verbatim preserved
    assert "\u2026" in text  # summary was truncated with an ellipsis


def test_cap_quotes_per_theme():
    # X5.10 (per-theme overflow) — only max_quotes_per_theme quotes rendered.
    theme = _theme("Perf", "s", quotes=[f"verbatim quote number {i} here" for i in range(6)],
                   actions=["a"], who=["Product"])
    cfg = Settings(render={"max_quotes_per_theme": 2}).render
    reqs = _build([theme], cfg=cfg)
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    rendered = sum(1 for i in range(6) if f"verbatim quote number {i} here" in text)
    assert rendered == 2


def test_special_chars_literal_in_docs_text():
    # X5.4 — Docs inserts are literal text (no HTML escaping, not corrupted).
    theme = _theme("Bugs <b> & co", "Uses * and `backticks` and <tags>.",
                   quotes=["I said <hello> & \"bye\" 😀"], actions=["fix <x>"], who=["Product"])
    reqs = _build([theme])
    text = "".join(r["insertText"]["text"] for r in reqs if "insertText" in r)
    assert "I said <hello> & \"bye\" 😀" in text  # X5.5 emoji/unicode intact too
    assert "&amp;" not in text  # not HTML-escaped in Docs
