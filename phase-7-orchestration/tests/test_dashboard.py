"""Dashboard data upsert + HTML render tests."""

from __future__ import annotations

import json
from pathlib import Path

from pulse.render.dashboard import render_dashboard_html, upsert_run


def test_upsert_run_writes_data_and_html(tmp_path: Path):
    path = upsert_run(
        tmp_path,
        product_id="zepto",
        product_name="Zepto",
        doc_id="zepto-weekly-pulse",
        iso_week="2026-W28",
        fetch={
            "kept": 394,
            "input_total": 900,
            "source_counts": {"app_store": 500, "play_store": 400},
            "dropped": {"duplicates_exact": 10, "duplicates_near": 5, "out_of_window": 480, "quality": {"too_short": 11}},
            "window": ["2026-07-01", "2026-07-12"],
        },
        metrics={"themes": 8, "quotes_validated": 14, "reviews_in": 394, "latency_seconds": 1.2},
        section_anchor="pulse-zepto-2026-W28",
    )
    assert path.name == "dashboard-data.json"
    data = json.loads(path.read_text())
    assert data["runs"][0]["reviews_collected"] == 394
    assert data["runs"][0]["report_href"].endswith("#h.pulsezepto2026w28")

    html_path = tmp_path / "docs" / "dashboard.html"
    index_path = tmp_path / "docs" / "index.html"
    assert html_path.is_file()
    assert index_path.is_file()
    body = html_path.read_text()
    assert "394" in body
    assert "Zepto" in body
    assert "Zepto" in body


def test_upsert_replaces_same_week(tmp_path: Path):
    upsert_run(
        tmp_path,
        product_id="zepto",
        product_name="Zepto",
        doc_id="zepto-weekly-pulse",
        iso_week="2026-W28",
        fetch={"kept": 100, "input_total": 200, "source_counts": {}, "dropped": {}},
        metrics={"themes": 1, "quotes_validated": 0},
    )
    upsert_run(
        tmp_path,
        product_id="zepto",
        product_name="Zepto",
        doc_id="zepto-weekly-pulse",
        iso_week="2026-W28",
        fetch={"kept": 394, "input_total": 900, "source_counts": {"app_store": 1}, "dropped": {}},
        metrics={"themes": 8, "quotes_validated": 14},
    )
    data = json.loads((tmp_path / "docs" / "dashboard-data.json").read_text())
    assert len(data["runs"]) == 1
    assert data["runs"][0]["reviews_collected"] == 394


def test_render_empty_state():
    html = render_dashboard_html({"brand": "Zepto", "updated_at": None, "runs": []})
    assert "No runs recorded yet" in html
    assert "0" in html
    assert "#8B5CF6" in html or "8B5CF6" in html
