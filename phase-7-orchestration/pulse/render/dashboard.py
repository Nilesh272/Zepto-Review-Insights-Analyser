"""Static review-collection dashboard written beside the weekly Doc (local transport).

Each completed agent run upserts a week row into ``dashboard-data.json`` and regenerates
``dashboard.html`` / ``index.html`` under ``<local_output_dir>/docs/``.
"""

from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pulse.render.theme import DASHBOARD_CSS, FONT_LINK

logger = logging.getLogger("pulse.render.dashboard")

DATA_NAME = "dashboard-data.json"
DASHBOARD_NAME = "dashboard.html"
INDEX_NAME = "index.html"


def docs_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir) / "docs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load(path: Path) -> dict[str, Any]:
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("corrupt dashboard data at %s — starting fresh", path)
    return {"brand": "Zepto", "updated_at": None, "runs": []}


def upsert_run(
    output_dir: str | Path,
    *,
    product_id: str,
    product_name: str,
    doc_id: str,
    iso_week: str,
    fetch: dict[str, Any],
    metrics: dict[str, Any],
    section_anchor: str | None = None,
) -> Path:
    """Merge one week's ingestion metrics into the dashboard data file and rewrite HTML."""
    ddir = docs_dir(output_dir)
    data_path = ddir / DATA_NAME
    state = _load(data_path)

    kept = int(fetch.get("kept") or metrics.get("reviews_in") or 0)
    raw = int(fetch.get("input_total") or 0)
    sources = dict(fetch.get("source_counts") or {})
    dropped = dict(fetch.get("dropped") or {})
    window = list(fetch.get("window") or [])
    heading = "h." + "".join(c for c in (section_anchor or "").lower() if c.isalnum())
    report_href = f"{doc_id}.html"
    if heading != "h.":
        report_href = f"{report_href}#{heading}"

    row = {
        "product_id": product_id,
        "product_name": product_name,
        "doc_id": doc_id,
        "iso_week": iso_week,
        "reviews_collected": kept,
        "reviews_raw": raw,
        "source_counts": sources,
        "dropped": dropped,
        "window": window,
        "themes": int(metrics.get("themes") or 0),
        "quotes_validated": int(metrics.get("quotes_validated") or 0),
        "latency_seconds": metrics.get("latency_seconds"),
        "report_href": report_href,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    runs: list[dict[str, Any]] = [
        r for r in state.get("runs", [])
        if not (r.get("product_id") == product_id and r.get("iso_week") == iso_week)
    ]
    runs.append(row)
    runs.sort(key=lambda r: (r.get("iso_week") or "", r.get("product_id") or ""), reverse=True)

    state["brand"] = "Zepto"
    state["updated_at"] = row["recorded_at"]
    state["runs"] = runs
    data_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    html_body = render_dashboard_html(state)
    (ddir / DASHBOARD_NAME).write_text(html_body, encoding="utf-8")
    (ddir / INDEX_NAME).write_text(html_body, encoding="utf-8")
    logger.info(
        "dashboard updated: %s %s → %d reviews (%s)",
        product_id, iso_week, kept, ddir / DASHBOARD_NAME,
    )
    return data_path


def render_dashboard_html(state: dict[str, Any]) -> str:
    runs: list[dict[str, Any]] = list(state.get("runs") or [])
    latest = runs[0] if runs else None
    total_collected = sum(int(r.get("reviews_collected") or 0) for r in runs)
    total_raw = sum(int(r.get("reviews_raw") or 0) for r in runs)

    if latest:
        product = html.escape(str(latest.get("product_name") or latest.get("product_id") or "Product"))
        week = html.escape(str(latest.get("iso_week") or "—"))
        kept = int(latest.get("reviews_collected") or 0)
        raw = int(latest.get("reviews_raw") or 0)
        sources = latest.get("source_counts") or {}
        app_n = int(sources.get("app_store") or sources.get("appstore") or 0)
        play_n = int(sources.get("play_store") or sources.get("playstore") or 0)
        reddit_n = int(sources.get("reddit") or 0)
        community_n = sum(
            int(sources.get(k) or 0)
            for k in ("forum", "social", "product_review", "quick_commerce")
        )
        themes = int(latest.get("themes") or 0)
        report = html.escape(str(latest.get("report_href") or "#"))
        dropped = latest.get("dropped") or {}
        dropped_total = sum(int(v) for v in dropped.values() if isinstance(v, (int, float)))
        if isinstance(dropped.get("quality"), dict):
            dropped_total = (
                int(dropped.get("duplicates_exact") or 0)
                + int(dropped.get("duplicates_near") or 0)
                + int(dropped.get("out_of_window") or 0)
                + sum(int(v) for v in (dropped.get("quality") or {}).values())
            )
        source_chips = [
            ("App Store", app_n),
            ("Google Play", play_n),
            ("Reddit", reddit_n),
            ("Forums / social / QC", community_n),
        ]
    else:
        product, week, kept, raw = "—", "—", 0, 0
        themes = dropped_total = 0
        report = "#"
        source_chips = [("App Store", 0), ("Google Play", 0), ("Reddit", 0), ("Forums / social / QC", 0)]

    updated = html.escape(str(state.get("updated_at") or "—"))
    brand = html.escape(str(state.get("brand") or "Zepto"))

    chip_html = "\n".join(
        f'<div class="chip"><span>{html.escape(label)}</span><b>{n:,}</b></div>'
        for label, n in source_chips
    )

    rows_html: list[str] = []
    for r in runs:
        sc = r.get("source_counts") or {}
        href = html.escape(str(r.get("report_href") or "#"))
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('iso_week') or '—'))}</td>"
            f"<td>{html.escape(str(r.get('product_name') or r.get('product_id') or '—'))}</td>"
            f"<td class='num'>{int(r.get('reviews_collected') or 0):,}</td>"
            f"<td class='num'>{int(r.get('reviews_raw') or 0):,}</td>"
            f"<td class='num'>{int(sc.get('app_store') or sc.get('appstore') or 0):,}</td>"
            f"<td class='num'>{int(sc.get('play_store') or sc.get('playstore') or 0):,}</td>"
            f"<td class='num'>{int(sc.get('reddit') or 0):,}</td>"
            f"<td class='num'>{sum(int(sc.get(k) or 0) for k in ('forum','social','product_review','quick_commerce')):,}</td>"
            f"<td class='num'>{int(r.get('themes') or 0)}</td>"
            f"<td><a href='{href}'>Open report</a></td>"
            "</tr>"
        )
    table_body = "\n".join(rows_html) if rows_html else (
        "<tr><td colspan='10' class='empty'>No runs recorded yet.</td></tr>"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand} — Review Pulse</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="{FONT_LINK}" rel="stylesheet">
<style>
{DASHBOARD_CSS}
</style>
</head>
<body>
  <div class="wrap">
    <h1 class="brand"><span>{brand}</span> Pulse</h1>
    <p class="lede">Review collection for {product}. Counts update automatically after each weekly agent run.</p>

    <div class="hero">
      <div class="stat-main">
        <p class="label">Reviews collected · latest week</p>
        <p class="value">{kept:,}</p>
        <p class="meta">
          <strong>{product}</strong> · {week}
          {" · " + f"{raw:,} fetched before filters" if raw else ""}
        </p>
      </div>
      <div class="side">
{chip_html}
        <div class="chip"><span>Dropped in filters</span><b>{dropped_total:,}</b></div>
        <div class="chip"><span>Insight themes</span><b>{themes}</b></div>
      </div>
    </div>

    <div class="actions">
      <a class="primary" href="{report}">Open latest insight report</a>
      <a class="ghost" href="zepto-weekly-pulse.html">All weeks (HTML doc)</a>
    </div>

    <div class="panel">
      <h2>Collection history</h2>
      <p class="hint">
        Lifetime kept across recorded runs: <strong>{total_collected:,}</strong>
        {" · raw fetched: " + f"{total_raw:,}" if total_raw else ""}.
      </p>
      <table>
        <thead>
          <tr>
            <th>Week</th>
            <th>Product</th>
            <th class="num">Collected</th>
            <th class="num">Raw</th>
            <th class="num">App Store</th>
            <th class="num">Play</th>
            <th class="num">Reddit</th>
            <th class="num">Community</th>
            <th class="num">Themes</th>
            <th>Report</th>
          </tr>
        </thead>
        <tbody>
{table_body}
        </tbody>
      </table>
    </div>

    <footer>Updated {updated} · data file <code>{DATA_NAME}</code></footer>
  </div>
</body>
</html>
"""
