"""Generic stdio MCP adapter — mapping logic, exercised with a fake session (no SDK/network).

Validates that the agent's typed Docs/Gmail operations are translated into the configured tool
names + argument keys, and that results are normalized back into the shapes the delivery layer
(`docs_mcp` / `gmail_mcp`) expects.
"""

import pytest

from pulse.config import DocsToolMap, GmailToolMap
from pulse.delivery.mcp_client import McpError
from pulse.delivery.stdio_mcp import StdioDocsClient, StdioGmailClient, _classify, _find_key


class FakeSession:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        resp = self.responses.get(name, {})
        return resp(arguments) if callable(resp) else resp


ANCHOR = "pulse-spotify-2026-W26"


def test_docs_get_document_maps_named_ranges():
    sess = FakeSession({"get_document": {"namedRanges": {ANCHOR: {"headingId": "h.abc"}}}})
    client = StdioDocsClient(None, DocsToolMap(), session=sess)

    out = client.get_document("doc-1")
    assert out["namedRanges"][ANCHOR]["headingId"] == "h.abc"
    assert sess.calls == [("get_document", {"documentId": "doc-1"})]


def test_docs_get_document_custom_arg_and_keys():
    tools = DocsToolMap(get_document="docs.get", document_id_arg="document_id", named_ranges_key="ranges")
    sess = FakeSession({"docs.get": {"ranges": {ANCHOR: {"namedRangeId": "nr-9"}}}})
    client = StdioDocsClient(None, tools, session=sess)

    out = client.get_document("doc-1")
    assert out["namedRanges"][ANCHOR]["headingId"] == "nr-9"  # falls back to namedRangeId
    assert sess.calls == [("docs.get", {"document_id": "doc-1"})]


def test_docs_batch_update_returns_heading_id():
    sess = FakeSession({"batch_update": {"headingId": "h.new", "replies": [{}]}})
    client = StdioDocsClient(None, DocsToolMap(), session=sess)
    reqs = [{"createNamedRange": {"name": ANCHOR}}, {"insertText": {"text": "x"}}]

    out = client.batch_update("doc-1", reqs)
    assert out["headingId"] == "h.new"
    name, args = sess.calls[0]
    assert name == "batch_update" and args["documentId"] == "doc-1" and args["requests"] == reqs


def test_docs_batch_update_falls_back_to_anchor_slug():
    # Server returns nothing useful -> deep link still gets the anchor so a link is producible.
    sess = FakeSession({"batch_update": {"replies": [{}]}})
    client = StdioDocsClient(None, DocsToolMap(), session=sess)
    out = client.batch_update("doc-1", [{"createNamedRange": {"name": ANCHOR}}])
    assert out["headingId"] == ANCHOR


def test_docs_force_replace_requires_delete_tool():
    client = StdioDocsClient(None, DocsToolMap(), session=FakeSession())
    with pytest.raises(McpError):
        client.delete_section("doc-1", ANCHOR)

    tools = DocsToolMap(delete_named_range="delete_range")
    sess = FakeSession({"delete_range": {}})
    ok = StdioDocsClient(None, tools, session=sess)
    ok.delete_section("doc-1", ANCHOR)
    assert sess.calls == [("delete_range", {"documentId": "doc-1", "name": ANCHOR})]


def test_gmail_create_draft_and_send_map_args():
    sess = FakeSession({"create_draft": {"messageId": "d1"}, "send_message": {"messageId": "m1"}})
    client = StdioGmailClient(None, GmailToolMap(), session=sess)

    d = client.create_draft(to=["a@x.com"], subject="S", html="<p>h</p>", text="t")
    assert d == {"messageId": "d1", "status": "draft"}
    s = client.send_message(to=["a@x.com"], subject="S", html="<p>h</p>", text="t")
    assert s == {"messageId": "m1", "status": "sent"}
    assert sess.calls[0][1] == {"to": ["a@x.com"], "subject": "S", "html": "<p>h</p>", "text": "t"}


def test_requires_server_or_session():
    with pytest.raises(McpError):
        StdioDocsClient(None, DocsToolMap())
    with pytest.raises(McpError):
        StdioGmailClient(None, GmailToolMap())


def test_error_classification():
    from pulse.delivery.mcp_client import McpAuthError, McpNotFoundError, McpTransientError

    assert isinstance(_classify("Doc not found"), McpNotFoundError)
    assert isinstance(_classify("401 unauthorized"), McpAuthError)
    assert isinstance(_classify("request timed out"), McpTransientError)
    assert type(_classify("weird failure")) is McpError


def test_find_key_nested():
    assert _find_key({"a": {"b": {"messageId": "z"}}}, "messageId") == "z"
    assert _find_key([{"x": 1}, {"y": {"headingId": "h"}}], "headingId") == "h"
    assert _find_key({"a": 1}, "missing") is None
