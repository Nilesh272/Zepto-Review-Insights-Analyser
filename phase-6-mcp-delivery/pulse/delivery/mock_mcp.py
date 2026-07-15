"""In-process fake MCP servers (architecture §7) for local/dev/test delivery.

These emulate just the Google Docs MCP and Gmail MCP tools the agent uses, holding state in
memory so idempotency (anchor pre-check, no duplicate sends) is observable across calls within
a process. They contain **no Google SDK** — they stand in for the external MCP servers.

`shared_docs_client()` / `shared_gmail_client()` return per-process singletons so a `cli run`
sees consistent Doc/mailbox state; tests construct fresh instances for isolation.
"""

from __future__ import annotations

import re

from pulse.delivery.mcp_client import McpNotFoundError, McpTransientError


def _heading_id(anchor: str) -> str:
    # Deterministic + stable: the heading id is derived from the (stable) anchor (X6.10).
    return "h." + re.sub(r"[^a-z0-9]+", "", anchor.lower())


class MockDocsServer:
    """An in-memory stand-in for the Google Docs MCP server.

    Known doc ids must be pre-registered; unknown ids raise McpNotFoundError (X6.4).
    `fail_times` injects transient failures for retry testing (X6.6/E6.11).
    """

    def __init__(self, doc_ids: list[str] | None = None, *, fail_times: int = 0):
        # doc_id -> {"sections": {anchor: {...}}, "order": [anchor, ...]}
        self.docs: dict[str, dict] = {d: {"sections": {}, "order": []} for d in (doc_ids or [])}
        self._fail_times = fail_times
        self.batch_update_calls = 0

    def register_doc(self, doc_id: str) -> None:
        self.docs.setdefault(doc_id, {"sections": {}, "order": []})

    def _doc(self, doc_id: str) -> dict:
        if doc_id not in self.docs:
            raise McpNotFoundError(f"Doc not found: {doc_id!r}")
        return self.docs[doc_id]

    def get_document(self, doc_id: str) -> dict:
        doc = self._doc(doc_id)
        return {
            "documentId": doc_id,
            "namedRanges": {anchor: {"headingId": s["heading_id"]} for anchor, s in doc["sections"].items()},
            "order": list(doc["order"]),
        }

    def batch_update(self, doc_id: str, requests: list[dict]) -> dict:
        doc = self._doc(doc_id)
        if self._fail_times > 0:
            self._fail_times -= 1
            raise McpTransientError("simulated transient Docs MCP failure")
        self.batch_update_calls += 1

        anchors = [r["createNamedRange"]["name"] for r in requests if "createNamedRange" in r]
        if not anchors:
            raise McpTransientError("batch_update missing a named-range anchor")
        anchor = anchors[0]
        hid = _heading_id(anchor)
        doc["sections"][anchor] = {"heading_id": hid, "requests": requests}
        if anchor not in doc["order"]:
            doc["order"].append(anchor)
        return {"headingId": hid, "replies": [{} for _ in requests]}

    def delete_section(self, doc_id: str, anchor: str) -> None:
        doc = self._doc(doc_id)
        doc["sections"].pop(anchor, None)
        if anchor in doc["order"]:
            doc["order"].remove(anchor)

    def section_count(self, doc_id: str, anchor: str) -> int:
        return sum(1 for a in self._doc(doc_id)["order"] if a == anchor)


class MockGmailServer:
    """An in-memory stand-in for the Gmail MCP server."""

    def __init__(self, *, fail_times: int = 0):
        self.drafts: list[dict] = []
        self.sent: list[dict] = []
        self._fail_times = fail_times

    def _maybe_fail(self) -> None:
        if self._fail_times > 0:
            self._fail_times -= 1
            raise McpTransientError("simulated transient Gmail MCP failure")

    def create_draft(self, *, to, subject, html, text) -> dict:
        self._maybe_fail()
        msg = {"to": to, "subject": subject, "html": html, "text": text}
        msg_id = f"draft-{len(self.drafts) + 1}"
        self.drafts.append({**msg, "id": msg_id})
        return {"messageId": msg_id, "status": "draft"}

    def send_message(self, *, to, subject, html, text) -> dict:
        self._maybe_fail()
        msg = {"to": to, "subject": subject, "html": html, "text": text}
        msg_id = f"msg-{len(self.sent) + 1}"
        self.sent.append({**msg, "id": msg_id})
        return {"messageId": msg_id, "status": "sent"}


_SHARED_DOCS: MockDocsServer | None = None
_SHARED_GMAIL: MockGmailServer | None = None


def shared_docs_client() -> MockDocsServer:
    """Per-process Docs mock; auto-registers doc ids on first access via get/batch."""
    global _SHARED_DOCS
    if _SHARED_DOCS is None:
        _SHARED_DOCS = _AutoRegisterDocsServer()
    return _SHARED_DOCS


def shared_gmail_client() -> MockGmailServer:
    global _SHARED_GMAIL
    if _SHARED_GMAIL is None:
        _SHARED_GMAIL = MockGmailServer()
    return _SHARED_GMAIL


def reset_shared() -> None:
    """Reset per-process singletons (used between CLI runs / tests if needed)."""
    global _SHARED_DOCS, _SHARED_GMAIL
    _SHARED_DOCS = None
    _SHARED_GMAIL = None


class _AutoRegisterDocsServer(MockDocsServer):
    """For the shared/dev mock, treat any referenced Doc id as existing (no real Docs to seed)."""

    def _doc(self, doc_id: str) -> dict:
        self.register_doc(doc_id)
        return self.docs[doc_id]
