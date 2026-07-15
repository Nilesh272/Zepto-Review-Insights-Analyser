"""Local file delivery — reviews are actually written into an openable HTML doc, idempotently."""

import pytest

from pulse.config import Settings
from pulse.delivery.docs_mcp import append_section
from pulse.delivery.gmail_mcp import draft_or_send
from pulse.delivery.local_file_mcp import LocalFileDocsServer, LocalFileGmailServer
from tests.delivery_helpers import make_ctx, make_report

ANCHOR = "pulse-spotify-2026-W26"
DOC = "doc-spotify"


def _ctx(tmp_path, docs, gmail, **kw):
    return make_ctx(settings=Settings(email_mode="draft"), docs_mcp=docs, gmail_mcp=gmail,
                    doc_id=DOC, **kw)


def test_writes_doc_file_with_section_and_quotes(tmp_path):
    docs = LocalFileDocsServer(tmp_path)
    gmail = LocalFileGmailServer(tmp_path)
    report = make_report(product_id="spotify")
    ctx = _ctx(tmp_path, docs, gmail)

    hid = "h." + ANCHOR.replace("-", "").lower()
    out = append_section(ctx, report)
    assert out["appended"] is True
    assert out["deep_link"].startswith("file://") and out["deep_link"].endswith(f"#{hid}")

    html_file = tmp_path / "docs" / f"{DOC}.html"
    assert html_file.exists()
    content = html_file.read_text(encoding="utf-8")
    assert "Weekly Review Pulse" in content
    assert "App performance &amp; bugs" in content          # theme title, HTML-escaped
    assert "the app freezes at market open" in content      # verbatim quote
    assert f'id="{hid}"' in content                         # heading anchor

    email = draft_or_send(ctx, report, deep_link=out["deep_link"])
    assert email["email_status"] == "draft"
    drafts = list((tmp_path / "emails").glob("draft-*.html"))
    assert len(drafts) == 1


def test_idempotent_no_duplicate_section(tmp_path):
    docs = LocalFileDocsServer(tmp_path)
    report = make_report(product_id="spotify")
    ctx = _ctx(tmp_path, docs, LocalFileGmailServer(tmp_path))

    first = append_section(ctx, report)
    assert first["appended"] is True
    # A second backend instance reads the same files -> the section already exists.
    second = append_section(_ctx(tmp_path, LocalFileDocsServer(tmp_path), LocalFileGmailServer(tmp_path)), report)
    assert second["skipped"] is True
    assert docs.section_count(DOC, ANCHOR) == 1


def test_force_replaces_section(tmp_path):
    docs = LocalFileDocsServer(tmp_path)
    report = make_report(product_id="spotify")
    append_section(_ctx(tmp_path, docs, LocalFileGmailServer(tmp_path)), report)
    forced = append_section(_ctx(tmp_path, docs, LocalFileGmailServer(tmp_path), force=True), report)
    assert forced["replaced"] is True
    assert docs.section_count(DOC, ANCHOR) == 1


def test_low_signal_doc_still_written(tmp_path):
    docs = LocalFileDocsServer(tmp_path)
    report = make_report(product_id="spotify", low_signal=True)
    out = append_section(_ctx(tmp_path, docs, LocalFileGmailServer(tmp_path)), report)
    assert out["appended"] is True
    content = (tmp_path / "docs" / f"{DOC}.html").read_text(encoding="utf-8")
    assert "Low-signal week" in content
