"""E6.1/E6.2/E6.3/E6.4 + X6.2/X6.4 — Docs MCP append & idempotency (mock server)."""

import pytest

from pulse.delivery.docs_mcp import append_section, deep_link
from pulse.delivery.mcp_client import McpNotFoundError
from pulse.delivery.mock_mcp import MockDocsServer
from tests.delivery_helpers import make_ctx, make_report


def _server():
    return MockDocsServer(doc_ids=["doc-groww"])


def test_append_one_section_returns_heading_and_link():
    server = _server()
    ctx = make_ctx(docs_mcp=server)
    report = make_report()
    out = append_section(ctx, report)

    assert out["appended"] is True and out["skipped"] is False
    assert out["heading_id"]
    assert out["deep_link"] == deep_link("doc-groww", out["heading_id"])
    assert server.section_count("doc-groww", report.section_anchor) == 1


def test_idempotent_skip_on_rerun_without_force():
    # E6.2 anchor pre-check + E6.3 no duplicate section.
    server = _server()
    report = make_report()
    append_section(make_ctx(docs_mcp=server), report)
    out2 = append_section(make_ctx(docs_mcp=server), report)

    assert out2["appended"] is False and out2["skipped"] is True
    assert server.section_count("doc-groww", report.section_anchor) == 1
    assert server.batch_update_calls == 1  # second run did not write


def test_force_replaces_without_duplicating():
    # E6.4 / X6.2 — force deletes then re-appends; still exactly one section.
    server = _server()
    report = make_report()
    append_section(make_ctx(docs_mcp=server), report)
    out2 = append_section(make_ctx(docs_mcp=server, force=True), report)

    assert out2["appended"] is True and out2["replaced"] is True
    assert server.section_count("doc-groww", report.section_anchor) == 1
    assert server.batch_update_calls == 2


def test_unknown_doc_id_fails_fast():
    # X6.4 — wrong/missing Doc id surfaces as not-found, no fallback.
    server = MockDocsServer(doc_ids=["some-other-doc"])
    with pytest.raises(McpNotFoundError):
        append_section(make_ctx(docs_mcp=server, doc_id="doc-groww"), make_report())


def test_heading_id_stable_across_reruns():
    # X6.10 — anchor stable => heading id stable => deep link resolves consistently.
    server = _server()
    report = make_report()
    a = append_section(make_ctx(docs_mcp=server), report)["heading_id"]
    b = append_section(make_ctx(docs_mcp=server, force=True), report)["heading_id"]
    assert a == b
