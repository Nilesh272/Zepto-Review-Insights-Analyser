"""X7.13 — partial success (Doc appended, email failed) completes email-only on re-run."""

import pytest

from pulse.config import Settings
from pulse.delivery.docs_mcp import append_section
from pulse.delivery.gmail_mcp import draft_or_send
from pulse.delivery.mcp_client import McpError
from pulse.delivery.mock_mcp import MockDocsServer, MockGmailServer
from tests.delivery_helpers import make_ctx, make_report

ANCHOR = "pulse-groww-2026-W26"
DOC = "doc-groww"


class _FailingGmail:
    def create_draft(self, **kw):
        raise McpError("gmail down (permanent)")

    def send_message(self, **kw):
        raise McpError("gmail down (permanent)")


def test_partial_then_email_only_completes():
    docs = MockDocsServer(doc_ids=[DOC])
    report = make_report()

    # --- Run 1: Doc append succeeds, email delivery fails. ---
    ctx1 = make_ctx(settings=Settings(email_mode="draft"), docs_mcp=docs, gmail_mcp=_FailingGmail())
    appended = append_section(ctx1, report)
    assert appended["appended"] is True
    with pytest.raises(McpError):
        draft_or_send(ctx1, report, deep_link=appended["deep_link"])

    assert docs.section_count(DOC, ANCHOR) == 1  # section is there

    # --- Run 2: prior shows the section but no email; re-run skips append, drafts email. ---
    gmail = MockGmailServer()
    ctx2 = make_ctx(
        settings=Settings(email_mode="draft"), docs_mcp=docs, gmail_mcp=gmail,
        prior_delivery={"email_status": "none", "doc_id": DOC, "deep_link": appended["deep_link"]},
    )
    re_appended = append_section(ctx2, report)
    assert re_appended["skipped"] is True  # anchor already present -> no duplicate section

    out = draft_or_send(ctx2, report, deep_link=re_appended["deep_link"])
    assert out["email_status"] == "draft" and out["skipped"] is False
    assert docs.section_count(DOC, ANCHOR) == 1  # still exactly one section
    assert len(gmail.drafts) == 1
