"""E7.9 / X7.11 — EMAIL_MODE send gating is fail-safe."""

from pulse.cli import resolve_email_mode


def test_unset_keeps_configured_default():
    assert resolve_email_mode("draft", env={}) == "draft"
    assert resolve_email_mode("send", env={}) == "send"


def test_explicit_send_enables_send():
    assert resolve_email_mode("draft", env={"EMAIL_MODE": "send"}) == "send"
    assert resolve_email_mode("draft", env={"EMAIL_MODE": "SEND"}) == "send"


def test_explicit_draft():
    assert resolve_email_mode("send", env={"EMAIL_MODE": "draft"}) == "draft"


def test_misconfigured_defaults_to_draft():
    # X7.11 — any non-send/draft value resolves to the safe 'draft'.
    assert resolve_email_mode("send", env={"EMAIL_MODE": "yes-please"}) == "draft"
    assert resolve_email_mode("send", env={"EMAIL_MODE": ""}) == "draft"
