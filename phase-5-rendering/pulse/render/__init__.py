"""Rendering layer (architecture §3.2 `render_report`, §7.3).

Phase 5 turns grounded `Theme[]` into:
  - Google Docs `batchUpdate` requests for a new dated, anchored section (`docs.py`), and
  - a teaser email with HTML + plain-text parts and a deep-link placeholder (`email.py`).

No live MCP calls happen here; delivery (and filling the deep link) lands in Phase 6.
"""
