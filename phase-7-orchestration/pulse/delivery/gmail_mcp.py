"""`gmail_mcp.draft_or_send` — deliver the teaser email via the Gmail MCP (architecture §3.3,
§7.2, §7.3).

  - Injects the real Doc deep link into the email (E6.8).
  - Validates recipients before sending; empty/invalid → skip + flag, never error-send (X6.14).
  - `EMAIL_MODE=draft` creates a draft (dev/staging, E6.5/X6.8); `send` sends once (prod, E6.6).
  - Idempotent: if the ledger already recorded a draft/send for this run key, reuse it rather
    than re-delivering (E6.7 / X6.7). `--force` re-delivers per the current mode.

All calls go through the MCP client; transient failures are retried with backoff (X6.6/E6.11).
"""

from __future__ import annotations

import logging
import re

from pulse.delivery.mcp_client import build_gmail_client, with_mcp_retries
from pulse.render.email import fill_deep_link

logger = logging.getLogger("pulse.delivery.gmail")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_recipients(recipients) -> list[str]:
    return [r for r in (recipients or []) if isinstance(r, str) and _EMAIL_RE.match(r.strip())]


def draft_or_send(ctx, report, *, deep_link: str, client=None) -> dict:
    """Draft or send the teaser email. Returns email delivery state."""
    prior = ctx.bag.get("prior_delivery", {}) or {}
    if not ctx.force and prior.get("email_status") in {"draft", "sent"}:
        logger.info("email already %s for this run key — skipping (idempotent)", prior["email_status"])
        return {
            "email_status": prior["email_status"],
            "message_id": prior.get("message_id"),
            "skipped": True,
            "mode": ctx.settings.email_mode,
        }

    recipients = ctx.product.recipients if ctx.product else []
    valid = valid_recipients(recipients)
    if not valid:
        logger.warning("no valid recipients configured — skipping email (flagged)")
        return {"email_status": "none", "message_id": None, "skipped": True,
                "reason": "no_valid_recipients", "mode": ctx.settings.email_mode}

    cfg = ctx.settings.render
    email = fill_deep_link(report.email, deep_link, cfg)  # E6.8 deep link into the teaser

    client = client or ctx.gmail_mcp or build_gmail_client(ctx.settings)
    mcp = ctx.settings.mcp
    mode = ctx.settings.email_mode
    op = client.create_draft if mode == "draft" else client.send_message

    result = with_mcp_retries(
        lambda: op(to=valid, subject=email.subject, html=email.html, text=email.text),
        max_retries=mcp.max_retries,
        backoff_seconds=mcp.retry_backoff_seconds,
        label=f"gmail.{mode}",
    )
    status = "draft" if mode == "draft" else "sent"
    logger.info("email %s to %d recipient(s): %s", status, len(valid), result["messageId"])
    return {
        "email_status": status,
        "message_id": result["messageId"],
        "skipped": False,
        "recipients": valid,
        "mode": mode,
    }
