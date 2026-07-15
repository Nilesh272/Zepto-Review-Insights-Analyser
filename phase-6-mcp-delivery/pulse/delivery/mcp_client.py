"""MCP client interfaces + transport selection (architecture §7).

The agent talks to two MCP servers through small typed clients. Each method maps to a logical
MCP tool call (architecture §7.2). Errors are normalized so the delivery layer can distinguish:

  - McpTransientError — retryable (timeout/unreachable/5xx): retried with backoff (X6.6/E6.11).
  - McpAuthError      — surfaced as-is; the agent never holds/refreshes Google creds (X6.5).
  - McpNotFoundError  — fail fast, no REST fallback (X6.4).
  - McpError          — base for other permanent failures.

Transport:
  - "mock"  → in-process fake servers (local/dev/tests), shared per-process so idempotency is
              observable across calls.
  - "stdio" → a real MCP server over the configured endpoint (requires an MCP SDK; not used in
              offline tests). Importing/using it never pulls in a Google SDK.
"""

from __future__ import annotations

import logging
from typing import Callable, Protocol, TypeVar

logger = logging.getLogger("pulse.delivery")

T = TypeVar("T")


class McpError(RuntimeError):
    """Base class for MCP delivery failures."""


class McpTransientError(McpError):
    """Retryable transient failure (timeout, unreachable, 5xx)."""


class McpAuthError(McpError):
    """Authentication/authorization failure surfaced by the MCP server (token expired, etc.)."""


class McpNotFoundError(McpError):
    """A referenced resource (e.g. the Doc id) does not exist."""


class DocsMcpClient(Protocol):
    def get_document(self, doc_id: str) -> dict: ...
    def batch_update(self, doc_id: str, requests: list[dict]) -> dict: ...
    def delete_section(self, doc_id: str, anchor: str) -> None: ...


class GmailMcpClient(Protocol):
    def create_draft(self, *, to: list[str], subject: str, html: str, text: str) -> dict: ...
    def send_message(self, *, to: list[str], subject: str, html: str, text: str) -> dict: ...


def with_mcp_retries(
    fn: Callable[[], T],
    *,
    max_retries: int,
    backoff_seconds: float,
    sleep: Callable[[float], None] | None = None,
    label: str = "mcp call",
) -> T:
    """Retry only on McpTransientError; permanent errors (auth/not-found) propagate immediately."""
    import time

    sleep = sleep or time.sleep
    attempt = 0
    while True:
        try:
            return fn()
        except McpTransientError as exc:
            attempt += 1
            if attempt > max_retries:
                logger.warning("%s failed after %d attempts: %s", label, attempt, exc)
                raise
            delay = backoff_seconds * (2 ** (attempt - 1))
            logger.info("%s transient failure (attempt %d), retrying in %.2fs", label, attempt, delay)
            sleep(delay)


def build_docs_client(settings) -> DocsMcpClient:
    if settings.mcp.transport == "mock":
        from pulse.delivery.mock_mcp import shared_docs_client

        return shared_docs_client()
    from pulse.delivery.stdio_mcp import StdioDocsClient  # noqa: PLC0415

    return StdioDocsClient(settings.mcp.docs_endpoint)


def build_gmail_client(settings) -> GmailMcpClient:
    if settings.mcp.transport == "mock":
        from pulse.delivery.mock_mcp import shared_gmail_client

        return shared_gmail_client()
    from pulse.delivery.stdio_mcp import StdioGmailClient  # noqa: PLC0415

    return StdioGmailClient(settings.mcp.gmail_endpoint)
