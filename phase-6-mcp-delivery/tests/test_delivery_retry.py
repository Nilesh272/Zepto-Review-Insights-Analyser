"""E6.11 + X6.6 — transient MCP failures retried with backoff; eventual failure is clean."""

import pytest

from pulse.config import Settings
from pulse.delivery.docs_mcp import append_section
from pulse.delivery.mcp_client import McpTransientError, with_mcp_retries
from pulse.delivery.mock_mcp import MockDocsServer
from tests.delivery_helpers import make_ctx, make_report


def _no_sleep(_):
    return None


def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise McpTransientError("boom")
        return "ok"

    assert with_mcp_retries(flaky, max_retries=3, backoff_seconds=0, sleep=_no_sleep) == "ok"
    assert calls["n"] == 3


def test_retry_gives_up_and_raises():
    def always():
        raise McpTransientError("down")

    with pytest.raises(McpTransientError):
        with_mcp_retries(always, max_retries=2, backoff_seconds=0, sleep=_no_sleep)


def test_append_retries_then_succeeds():
    # Docs server fails twice transiently on batch_update, then succeeds; one section written.
    server = MockDocsServer(doc_ids=["doc-groww"], fail_times=2)
    settings = Settings()
    settings.mcp.retry_backoff_seconds = 0  # fast test
    ctx = make_ctx(settings=settings, docs_mcp=server)
    report = make_report()
    out = append_section(ctx, report)
    assert out["appended"] is True
    assert server.section_count("doc-groww", report.section_anchor) == 1
