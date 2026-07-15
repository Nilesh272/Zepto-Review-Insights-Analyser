"""E6.5/E6.6/E6.7/E6.8 + X6.8/X6.14 — Gmail MCP draft/send, idempotency, deep link."""

from pulse.config import Settings
from pulse.delivery.gmail_mcp import draft_or_send, valid_recipients
from pulse.delivery.mock_mcp import MockGmailServer
from tests.delivery_helpers import make_ctx, make_report

LINK = "https://docs.google.com/document/d/doc-groww/edit#heading=h.abc"


def test_draft_mode_creates_draft_only():
    # E6.5 / X6.8 — dev default drafts, nothing sent.
    server = MockGmailServer()
    ctx = make_ctx(settings=Settings(email_mode="draft"), gmail_mcp=server)
    out = draft_or_send(ctx, make_report(), deep_link=LINK)

    assert out["email_status"] == "draft" and out["message_id"].startswith("draft-")
    assert len(server.drafts) == 1 and len(server.sent) == 0


def test_send_mode_sends_once():
    # E6.6 — prod sends exactly one.
    server = MockGmailServer()
    ctx = make_ctx(settings=Settings(email_mode="send"), gmail_mcp=server)
    out = draft_or_send(ctx, make_report(), deep_link=LINK)

    assert out["email_status"] == "sent" and out["message_id"].startswith("msg-")
    assert len(server.sent) == 1 and len(server.drafts) == 0


def test_deep_link_injected_into_delivered_email():
    # E6.8 — the link targets the new heading and the placeholder is gone.
    server = MockGmailServer()
    ctx = make_ctx(settings=Settings(email_mode="send"), gmail_mcp=server)
    draft_or_send(ctx, make_report(), deep_link=LINK)

    sent = server.sent[0]
    token = Settings().render.deep_link_token
    assert LINK in sent["html"] and LINK in sent["text"]
    assert token not in sent["html"] and token not in sent["text"]


def test_email_idempotent_when_prior_sent():
    # E6.7 / X6.7 — ledger already shows a send => skip, reuse message id.
    server = MockGmailServer()
    ctx = make_ctx(
        settings=Settings(email_mode="send"), gmail_mcp=server,
        prior_delivery={"email_status": "sent", "message_id": "msg-prev"},
    )
    out = draft_or_send(ctx, make_report(), deep_link=LINK)

    assert out["skipped"] is True and out["message_id"] == "msg-prev"
    assert len(server.sent) == 0  # nothing re-sent


def test_no_valid_recipients_skips_send():
    # X6.14 — empty/invalid recipients: skip + flag, never error-send.
    server = MockGmailServer()
    ctx = make_ctx(settings=Settings(email_mode="send"), gmail_mcp=server, recipients=["not-an-email"])
    out = draft_or_send(ctx, make_report(), deep_link=LINK)

    assert out["email_status"] == "none" and out["skipped"] is True
    assert out["reason"] == "no_valid_recipients"
    assert len(server.sent) == 0


def test_valid_recipients_filter():
    assert valid_recipients(["a@b.com", "bad", "c@d.co"]) == ["a@b.com", "c@d.co"]
    assert valid_recipients([]) == []
