"""E5.5/E5.6/E5.7 + X5.4/X5.8/X5.9 — teaser email rendering."""

from pulse.config import Settings
from pulse.models import Quote, Theme
from pulse.render.email import fill_deep_link, has_unfilled_deep_link, render_email


def _theme(title, summary, quote=None):
    quotes = [Quote(text=quote, review_id="r0", validated=True)] if quote else []
    return Theme(title=title, summary=summary, quotes=quotes, actions=["do x"], who_this_helps=["Product"])


THEMES = [
    _theme("App performance & bugs", "Crashes during trading.", quote="the app freezes at market open"),
    _theme("Customer support friction", "Slow responses."),
]
CFG = Settings().render


def _email(themes=THEMES, low_signal=False):
    return render_email(themes, product_name="Groww", iso_week="2026-W26", cfg=CFG, low_signal=low_signal)


def test_multipart_html_and_text():
    # E5.5 — both parts present and non-empty.
    e = _email()
    assert e.html.startswith("<!doctype html>") and "<h2>" in e.html
    assert "Groww — Weekly Review Pulse (2026-W26)" in e.text
    assert e.subject == "Weekly Review Pulse — Groww (2026-W26)"


def test_teaser_only_titles_not_full_report():
    # E5.6 — theme titles as bullets, but NOT quotes/actions (that's the Doc's job).
    e = _email()
    assert "App performance &amp; bugs" in e.html  # title escaped in HTML
    assert "App performance & bugs" in e.text
    assert "the app freezes at market open" not in e.html  # quote text not in teaser
    assert "do x" not in e.html  # actions not in teaser


def test_deep_link_placeholder_present_and_flagged():
    # E5.7 / X5.9 — placeholder present, unfilled until Phase 6.
    e = _email()
    assert CFG.deep_link_token in e.html
    assert CFG.deep_link_token in e.text
    assert e.deep_link_filled is False
    assert has_unfilled_deep_link(e, CFG) is True


def test_fill_deep_link():
    e = _email()
    filled = fill_deep_link(e, "https://docs.google.com/document/d/abc/edit#heading=h.1", CFG)
    assert filled.deep_link_filled is True
    assert not has_unfilled_deep_link(filled, CFG)
    assert "https://docs.google.com/document/d/abc/edit#heading=h.1" in filled.html
    assert "https://docs.google.com/document/d/abc/edit#heading=h.1" in filled.text


def test_plaintext_self_sufficient_with_link():
    # X5.8 — if HTML is stripped, the text part still carries themes + the link.
    e = _email()
    assert "Top themes this week:" in e.text
    assert "App performance & bugs" in e.text
    assert "Read the full report:" in e.text


def test_html_escaping():
    # X5.4 — special chars escaped in HTML.
    themes = [_theme("Bugs <b> & co", "summary")]
    e = render_email(themes, product_name="A & B <Co>", iso_week="2026-W26", cfg=CFG)
    assert "Bugs &lt;b&gt; &amp; co" in e.html
    assert "A &amp; B &lt;Co&gt;" in e.html
    assert "<b>" not in e.html.replace("<body>", "")  # no raw injected tags from data


def test_low_signal_email():
    # X5.1 (email side) — clear low-signal message, still has the link slot.
    e = _email(themes=[], low_signal=True)
    assert "Low-signal week" in e.text and "Low-signal week" in e.html
    assert CFG.deep_link_token in e.text
