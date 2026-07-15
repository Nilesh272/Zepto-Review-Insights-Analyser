"""Teaser email rendering (architecture §7.3).

The email is a **teaser**: top theme titles as bullets plus a "Read full report" link — never a
duplicate of the full Doc report (E5.6). It carries a deep-link **placeholder** that Phase 6
fills after the Doc write (E5.7 / X5.9). Both an HTML part and a self-sufficient plain-text part
are produced (E5.5 / X5.8), with all dynamic text HTML-escaped (X5.4 / X5.9).
"""

from __future__ import annotations

from html import escape

from pulse.models import EmailDraft


def _theme_titles(themes) -> list[str]:
    return [t.title for t in themes]


def render_email(
    themes,
    *,
    product_name: str,
    iso_week: str,
    cfg,
    low_signal: bool = False,
    insight_mode: bool = False,
) -> EmailDraft:
    """Render the teaser email with an unfilled deep-link slot."""
    subject = cfg.subject_template.format(product=product_name, week=iso_week)
    link = cfg.deep_link_token
    titles = _theme_titles(themes)
    section = "Key insights this week:" if insight_mode else "Top themes this week:"

    # ----- plain text (self-sufficient even if HTML is stripped, X5.8) -----
    text_lines = [
        f"{product_name} — Weekly Review Pulse ({iso_week})",
        "",
    ]
    if low_signal or not titles:
        text_lines.append("Low-signal week: too few reviews to extract reliable themes.")
    else:
        text_lines.append(section)
        text_lines += [f"  - {t}" for t in titles]
    text_lines += ["", f"Read the full report: {link}"]
    text = "\n".join(text_lines)

    # ----- HTML -----
    esc_product = escape(product_name)
    esc_week = escape(iso_week)
    if low_signal or not titles:
        body_html = "<p>Low-signal week: too few reviews to extract reliable themes.</p>"
    else:
        items = "".join(f"<li>{escape(t)}</li>" for t in titles)
        body_html = f"<p>{escape(section)}</p><ul>{items}</ul>"
    html = (
        f"<!doctype html><html><body>"
        f"<h2>{esc_product} — Weekly Review Pulse ({esc_week})</h2>"
        f"{body_html}"
        f'<p><a href="{escape(link)}">Read full report</a></p>'
        f"</body></html>"
    )

    return EmailDraft(subject=subject, html=html, text=text, deep_link_filled=False)


def has_unfilled_deep_link(email: EmailDraft, cfg) -> bool:
    """True if the deep-link placeholder is still present (Phase 6 must fill before send, X5.9)."""
    token = cfg.deep_link_token
    return (token in email.html) or (token in email.text)


def fill_deep_link(email: EmailDraft, url: str, cfg) -> EmailDraft:
    """Return a copy with the placeholder replaced by the real Doc deep link (used in Phase 6)."""
    token = cfg.deep_link_token
    return email.model_copy(
        update={
            "html": email.html.replace(token, url),
            "text": email.text.replace(token, url),
            "deep_link_filled": True,
        }
    )
