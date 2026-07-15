"""`docs_mcp.append_section` — append the week's section via the Google Docs MCP (architecture
§3.3, §7.2, §8.1).

Idempotency by construction:
  - `get_document` first to check whether the section's stable anchor already exists (E6.2).
  - If it exists and not forced → skip the append, reuse the existing heading/deep link (E6.3).
  - If it exists and `force` → delete + re-append (clean replace, no duplicate) (E6.4 / X6.2).
  - Otherwise append exactly one dated section (E6.1).

All calls go through the MCP client; transient failures are retried with backoff (X6.6/E6.11),
auth/not-found errors propagate (X6.5/X6.4 — no REST fallback).
"""

from __future__ import annotations

import logging

from pulse.delivery.mcp_client import build_docs_client, with_mcp_retries

logger = logging.getLogger("pulse.delivery.docs")


def deep_link(doc_id: str, heading_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit#heading={heading_id}"


def append_section(ctx, report, *, client=None) -> dict:
    """Append (or idempotently skip/replace) the week's section. Returns delivery identifiers."""
    client = client or ctx.docs_mcp or build_docs_client(ctx.settings)
    doc_id = ctx.product.doc_id if ctx.product else None
    if not doc_id:
        raise ValueError("append_section requires a product with a configured doc_id")

    anchor = report.section_anchor
    mcp = ctx.settings.mcp

    def _retry(fn, label):
        return with_mcp_retries(
            fn, max_retries=mcp.max_retries, backoff_seconds=mcp.retry_backoff_seconds, label=label
        )

    doc = _retry(lambda: client.get_document(doc_id), "docs.get_document")
    existing = doc.get("namedRanges", {}).get(anchor)

    if existing and not ctx.force:
        hid = existing["headingId"]
        logger.info("anchor %s already present — skipping append (idempotent)", anchor)
        return {
            "doc_id": doc_id, "section_anchor": anchor, "heading_id": hid,
            "deep_link": deep_link(doc_id, hid), "appended": False, "replaced": False, "skipped": True,
        }

    replaced = False
    if existing and ctx.force:
        _retry(lambda: client.delete_section(doc_id, anchor), "docs.delete_section")
        replaced = True

    result = _retry(lambda: client.batch_update(doc_id, report.docs_requests), "docs.batch_update")
    hid = result["headingId"]
    logger.info("appended section %s (heading %s)%s", anchor, hid, " [replaced]" if replaced else "")
    return {
        "doc_id": doc_id, "section_anchor": anchor, "heading_id": hid,
        "deep_link": deep_link(doc_id, hid), "appended": True, "replaced": replaced, "skipped": False,
    }
