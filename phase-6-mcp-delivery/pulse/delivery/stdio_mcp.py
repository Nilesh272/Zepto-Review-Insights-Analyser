"""Real MCP transport (stdio) — thin clients over an MCP server (architecture §7).

These translate the typed client methods into MCP tool calls on the configured server. They
require an MCP client SDK and a running server; they are **not** exercised by the offline test
suite (which uses `transport: mock`). Crucially, this module imports **no Google SDK** — the
Google OAuth and Docs/Gmail API calls live entirely inside the MCP servers.
"""

from __future__ import annotations

from pulse.delivery.mcp_client import McpError


class _StdioBase:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self._session = None

    def _connect(self):
        try:
            import mcp  # type: ignore  # noqa: F401, PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional MCP SDK
            raise McpError(
                "Real MCP transport requires an MCP client SDK. Install it and configure the "
                f"server endpoint {self.endpoint!r}, or use transport: mock for local runs."
            ) from exc
        raise McpError(
            "Stdio MCP transport is a deployment integration point: wire the MCP session to "
            f"{self.endpoint!r} here. Use transport: mock for local/dev/test runs."
        )


class StdioDocsClient(_StdioBase):
    def get_document(self, doc_id: str) -> dict:  # pragma: no cover - integration point
        self._connect()

    def batch_update(self, doc_id: str, requests: list[dict]) -> dict:  # pragma: no cover
        self._connect()

    def delete_section(self, doc_id: str, anchor: str) -> None:  # pragma: no cover
        self._connect()


class StdioGmailClient(_StdioBase):
    def create_draft(self, **kwargs) -> dict:  # pragma: no cover - integration point
        self._connect()

    def send_message(self, **kwargs) -> dict:  # pragma: no cover - integration point
        self._connect()
