"""Local file delivery backend (architecture §7 — local stand-in).

Writes the weekly pulse to **real files on disk** so reviews are actually written into a document
you can open — with no Google credentials and no external MCP server. It implements the same
typed client interfaces as the MCP clients:

  - the "Doc" is an HTML file per product (`<output_dir>/docs/<doc_id>.html`), with one anchored
    section per ISO week, reconstructed faithfully from the Docs `batchUpdate` requests;
  - emails are written to `<output_dir>/emails/` as `.html` + `.txt`.

State lives on disk, so idempotency (anchor pre-check, no duplicate section) holds across separate
CLI runs. This module imports **no Google SDK** — it's a local sink, analogous to the mock server
but persistent and human-viewable.
"""

from __future__ import annotations

import html
import json
import logging
import re
from pathlib import Path

from pulse.render.theme import DOC_CSS, FONT_LINK

logger = logging.getLogger("pulse.delivery.local")


def _heading_id(anchor: str) -> str:
    return "h." + re.sub(r"[^a-z0-9]+", "", anchor.lower())


# --------------------------------------------------------------------------------------------------
# Reconstruct a readable section from the Docs batchUpdate requests
# --------------------------------------------------------------------------------------------------
def section_to_html(requests: list[dict], anchor: str) -> tuple[str, str]:
    """Render the ordered Docs requests into (html_fragment, plain_text) for one section."""
    paras: dict[int, dict] = {}
    order: list[int] = []
    for req in requests:
        if "insertText" in req:
            ins = req["insertText"]
            idx = ins["location"]["index"]
            paras[idx] = {"text": ins["text"].rstrip("\n"), "style": "NORMAL_TEXT",
                          "bullet": False, "italic": False, "anchor": None}
            order.append(idx)
        elif "updateParagraphStyle" in req:
            ups = req["updateParagraphStyle"]
            start = ups["range"]["startIndex"]
            if start in paras:
                paras[start]["style"] = ups["paragraphStyle"]["namedStyleType"]
        elif "createParagraphBullets" in req:
            rng = req["createParagraphBullets"]["range"]
            for idx in order:
                if rng["startIndex"] <= idx < rng["endIndex"]:
                    paras[idx]["bullet"] = True
        elif "updateTextStyle" in req:
            uts = req["updateTextStyle"]
            if uts.get("textStyle", {}).get("italic"):
                rng = uts["range"]
                for idx in order:
                    if rng["startIndex"] <= idx < rng["endIndex"]:
                        paras[idx]["italic"] = True
        elif "createNamedRange" in req:
            cnr = req["createNamedRange"]
            start = cnr["range"]["startIndex"]
            if start in paras:
                paras[start]["anchor"] = cnr["name"]

    html_parts: list[str] = []
    text_parts: list[str] = []
    in_list = False

    def _close_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for idx in order:
        p = paras[idx]
        esc = html.escape(p["text"])
        text_parts.append(p["text"])
        if p["bullet"]:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            inner = f"<em>{esc}</em>" if p["italic"] else esc
            html_parts.append(f"  <li>{inner}</li>")
            continue
        _close_list()
        if p["style"] == "HEADING_1":
            aid = f' id="{html.escape(_heading_id(p["anchor"]))}"' if p["anchor"] else ""
            html_parts.append(f"<h1{aid}>{esc}</h1>")
        elif p["style"] == "HEADING_2":
            html_parts.append(f"<h2>{esc}</h2>")
        else:
            html_parts.append(f"<p>{esc}</p>")
    _close_list()
    return "\n".join(html_parts), "\n".join(text_parts)


_DOC_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{font_link}" rel="stylesheet">
</head>
<body>
<div class="banner">
  <p class="eyebrow">Zepto · AI review pulse</p>
  <h1>{title}</h1>
  <p>Research questions answered from App Store &amp; Google Play reviews at scale. Quotes are verbatim and grounded.</p>
</div>
{body}
</body>
</html>
"""


class LocalFileDocsServer:
    """A persistent, file-backed stand-in for the Google Docs MCP server."""

    def __init__(self, output_dir: str | Path):
        self.docs_dir = Path(output_dir) / "docs"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self, doc_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", doc_id)
        return self.docs_dir / f"{safe}.json"

    def _html_path(self, doc_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", doc_id)
        return self.docs_dir / f"{safe}.html"

    def _load(self, doc_id: str) -> dict:
        path = self._state_path(doc_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"doc_id": doc_id, "title": f"Weekly Review Pulse — {doc_id}", "sections": {}, "order": []}

    def _save(self, doc_id: str, state: dict) -> None:
        self._state_path(doc_id).write_text(json.dumps(state, indent=2), encoding="utf-8")
        body = "\n".join(
            f'<section>\n{state["sections"][a]["html"]}\n</section>' for a in state["order"]
        )
        page = _DOC_TEMPLATE.format(
            title=html.escape(state["title"]),
            body=body,
            css=DOC_CSS,
            font_link=FONT_LINK,
        )
        self._html_path(doc_id).write_text(page, encoding="utf-8")

    def deep_link(self, doc_id: str, heading_id: str) -> str:
        # as_uri() percent-encodes spaces/specials so the link works when clicked or pasted.
        return f"{self._html_path(doc_id).resolve().as_uri()}#{heading_id}"

    def get_document(self, doc_id: str) -> dict:
        state = self._load(doc_id)
        ranges = {a: {"headingId": state["sections"][a]["heading_id"]} for a in state["order"]}
        return {"namedRanges": ranges, "order": list(state["order"])}

    def batch_update(self, doc_id: str, requests: list[dict]) -> dict:
        anchor = next((r["createNamedRange"]["name"] for r in requests if "createNamedRange" in r), None)
        if not anchor:
            raise ValueError("batch_update requires a createNamedRange anchor")
        frag, _text = section_to_html(requests, anchor)
        hid = _heading_id(anchor)
        state = self._load(doc_id)
        state["sections"][anchor] = {"html": frag, "heading_id": hid}
        if anchor not in state["order"]:
            state["order"].append(anchor)
        self._save(doc_id, state)
        logger.info("wrote section %s to %s", anchor, self._html_path(doc_id))
        return {"headingId": hid, "replies": [{} for _ in requests]}

    def delete_section(self, doc_id: str, anchor: str) -> None:
        state = self._load(doc_id)
        state["sections"].pop(anchor, None)
        if anchor in state["order"]:
            state["order"].remove(anchor)
        self._save(doc_id, state)

    def section_count(self, doc_id: str, anchor: str) -> int:
        return sum(1 for a in self._load(doc_id)["order"] if a == anchor)


class LocalFileGmailServer:
    """A persistent, file-backed stand-in for the Gmail MCP server."""

    def __init__(self, output_dir: str | Path):
        self.emails_dir = Path(output_dir) / "emails"
        self.emails_dir.mkdir(parents=True, exist_ok=True)

    def _write(self, status: str, *, to, subject, html_body, text) -> dict:
        slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60] or "email"
        stem = f"{status}-{slug}"
        (self.emails_dir / f"{stem}.html").write_text(html_body, encoding="utf-8")
        (self.emails_dir / f"{stem}.txt").write_text(
            f"To: {', '.join(to)}\nSubject: {subject}\n\n{text}", encoding="utf-8"
        )
        logger.info("wrote %s email to %s", status, self.emails_dir / f"{stem}.html")
        return {"messageId": stem, "status": status}

    def create_draft(self, *, to, subject, html, text) -> dict:
        return self._write("draft", to=to, subject=subject, html_body=html, text=text)

    def send_message(self, *, to, subject, html, text) -> dict:
        return self._write("sent", to=to, subject=subject, html_body=html, text=text)
