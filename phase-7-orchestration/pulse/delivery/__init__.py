"""Delivery boundary (architecture §3.3, §7).

This package is the **only** place that speaks MCP. It exposes two logical MCP tools to the
agent — `docs_mcp.append_section` and `gmail_mcp.draft_or_send` — backed by external MCP
servers (Google Docs MCP, Gmail MCP) that own the Google OAuth. The agent holds no Google
credentials and imports no Google SDK anywhere; swapping MCP servers touches only this package.
"""
