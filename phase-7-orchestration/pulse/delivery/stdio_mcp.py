"""Real MCP transport (stdio) — a generic, config-driven client over any MCP server (architecture §7).

These thin clients translate the agent's typed Docs/Gmail operations into MCP **tool calls** on a
server you launch (`mcp.docs_server` / `mcp.gmail_server`), using the tool names and argument/result
keys declared in `mcp.docs_tools` / `mcp.gmail_tools`. That keeps the agent decoupled from any one
server's schema — point the config at your server and go.

Crucially, this module imports **no Google SDK**: Google OAuth and the Docs/Gmail API calls live
entirely inside the MCP server process. The agent only speaks MCP.

The MCP Python SDK is async; `_StdioSession` wraps a persistent `ClientSession` on a private event
loop thread so the synchronous delivery layer can call it directly. The clients also accept an
injected `session` (any object with `call_tool(name, arguments) -> dict`) so the mapping logic is
unit-testable without the SDK or a live server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading

from pulse.config import DocsToolMap, GmailToolMap, StdioServerConfig
from pulse.delivery.mcp_client import (
    McpAuthError,
    McpError,
    McpNotFoundError,
    McpTransientError,
)

logger = logging.getLogger("pulse.delivery.stdio")


# --------------------------------------------------------------------------------------------------
# Result / error helpers
# --------------------------------------------------------------------------------------------------
def _text_of(result) -> str:
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def _classify(message: str) -> McpError:
    low = message.lower()
    if any(s in low for s in ("not found", "404", "no such", "does not exist")):
        return McpNotFoundError(message)
    if any(s in low for s in ("unauth", "401", "403", "permission", "forbidden", "token", "expired")):
        return McpAuthError(message)
    if any(s in low for s in ("timeout", "timed out", "unavailable", "503", "502", "connection")):
        return McpTransientError(message)
    return McpError(message)


def _parse_result(result) -> dict:
    """Normalize an MCP CallToolResult into a plain dict; raise a classified error on tool failure."""
    if getattr(result, "isError", False):
        raise _classify(_text_of(result) or "MCP tool reported an error")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    text = _text_of(result)
    if text:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except json.JSONDecodeError:
            return {"text": text}
    return {}


def _find_key(obj, key: str):
    """Depth-first search for the first value under `key` anywhere in a nested dict/list."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key(item, key)
            if found is not None:
                return found
    return None


# --------------------------------------------------------------------------------------------------
# Async stdio session, wrapped for synchronous use
# --------------------------------------------------------------------------------------------------
class _StdioSession:
    """Synchronous facade over an MCP stdio ClientSession running on a private loop thread."""

    def __init__(self, server: StdioServerConfig):
        self._server = server
        self._loop: asyncio.AbstractEventLoop | None = None
        self._session = None
        self._stdio_cm = None
        self._session_cm = None
        self._started = False
        self._lock = threading.Lock()

    def _submit(self, coro):
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def _ensure_started(self) -> None:
        with self._lock:
            if self._started:
                return
            try:
                from mcp import ClientSession, StdioServerParameters  # noqa: PLC0415
                from mcp.client.stdio import stdio_client  # noqa: PLC0415
            except ImportError as exc:  # pragma: no cover - depends on optional SDK
                raise McpError(
                    "Real MCP transport requires the MCP client SDK: `pip install mcp`. "
                    "Or use transport: mock for local/dev/test runs."
                ) from exc

            loop = asyncio.new_event_loop()
            threading.Thread(target=loop.run_forever, daemon=True).start()
            self._loop = loop

            async def _open():
                params = StdioServerParameters(
                    command=self._server.command,
                    args=list(self._server.args),
                    env={**os.environ, **self._server.env},
                )
                self._stdio_cm = stdio_client(params)
                read, write = await self._stdio_cm.__aenter__()
                self._session_cm = ClientSession(read, write)
                self._session = await self._session_cm.__aenter__()
                await self._session.initialize()

            try:
                self._submit(_open())
            except Exception as exc:  # noqa: BLE001 - normalize startup failures
                raise _classify(f"failed to start MCP server {self._server.command!r}: {exc}") from exc
            self._started = True
            logger.info("connected to MCP server %r", self._server.command)

    def call_tool(self, name: str, arguments: dict) -> dict:
        self._ensure_started()

        async def _call():
            return await self._session.call_tool(name, arguments=arguments)

        try:
            result = self._submit(_call())
        except McpError:
            raise
        except Exception as exc:  # noqa: BLE001 - transport/protocol errors -> transient
            raise McpTransientError(f"MCP tool {name!r} call failed: {exc}") from exc
        return _parse_result(result)

    def close(self) -> None:  # pragma: no cover - teardown best-effort
        if not self._started or self._loop is None:
            return

        async def _close():
            if self._session_cm is not None:
                await self._session_cm.__aexit__(None, None, None)
            if self._stdio_cm is not None:
                await self._stdio_cm.__aexit__(None, None, None)

        try:
            self._submit(_close())
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._started = False


# --------------------------------------------------------------------------------------------------
# Typed clients (match the Protocols in mcp_client.py)
# --------------------------------------------------------------------------------------------------
class StdioDocsClient:
    def __init__(self, server: StdioServerConfig | None, tools: DocsToolMap, *, session=None):
        if session is None and server is None:
            raise McpError("transport=stdio requires mcp.docs_server to be configured")
        self._tools = tools
        self._session = session if session is not None else _StdioSession(server)

    def get_document(self, doc_id: str) -> dict:
        res = self._session.call_tool(self._tools.get_document, {self._tools.document_id_arg: doc_id})
        named = res.get(self._tools.named_ranges_key) or {}
        ranges: dict[str, dict] = {}
        if isinstance(named, dict):
            for name, val in named.items():
                hid = None
                if isinstance(val, dict):
                    hid = val.get(self._tools.heading_id_key) or _find_key(val, "namedRangeId")
                ranges[name] = {"headingId": hid}
        return {"namedRanges": ranges, "order": list(ranges.keys())}

    def batch_update(self, doc_id: str, requests: list[dict]) -> dict:
        res = self._session.call_tool(
            self._tools.batch_update,
            {self._tools.document_id_arg: doc_id, self._tools.requests_arg: requests},
        )
        # Heading-level deep links aren't guaranteed by the Docs API; fall back to the named-range
        # id, then to the anchor slug, so a link is always produced.
        anchor = next(
            (r["createNamedRange"]["name"] for r in requests if "createNamedRange" in r), None
        )
        hid = (
            _find_key(res, self._tools.heading_id_key)
            or _find_key(res, "namedRangeId")
            or (anchor or "")
        )
        return {"headingId": hid, "replies": res.get("replies", [])}

    def delete_section(self, doc_id: str, anchor: str) -> None:
        if not self._tools.delete_named_range:
            raise McpError(
                "force replace needs mcp.docs_tools.delete_named_range set to your server's tool name"
            )
        self._session.call_tool(
            self._tools.delete_named_range,
            {self._tools.document_id_arg: doc_id, self._tools.name_arg: anchor},
        )


class StdioGmailClient:
    def __init__(self, server: StdioServerConfig | None, tools: GmailToolMap, *, session=None):
        if session is None and server is None:
            raise McpError("transport=stdio requires mcp.gmail_server to be configured")
        self._tools = tools
        self._session = session if session is not None else _StdioSession(server)

    def _args(self, *, to, subject, html, text) -> dict:
        t = self._tools
        return {t.to_arg: to, t.subject_arg: subject, t.html_arg: html, t.text_arg: text}

    def create_draft(self, *, to, subject, html, text) -> dict:
        res = self._session.call_tool(self._tools.create_draft, self._args(to=to, subject=subject, html=html, text=text))
        return {"messageId": _find_key(res, self._tools.message_id_key), "status": "draft"}

    def send_message(self, *, to, subject, html, text) -> dict:
        res = self._session.call_tool(self._tools.send_message, self._args(to=to, subject=subject, html=html, text=text))
        return {"messageId": _find_key(res, self._tools.message_id_key), "status": "sent"}
