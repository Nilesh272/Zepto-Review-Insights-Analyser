"""E7.7/E7.10/E7.11 + X7.8/X7.12 — metrics emission, budget halt, and the audit query."""

import pytest

from pulse.agent.core import AgentCore
from pulse.cli import audit_command
from pulse.delivery.mock_mcp import reset_shared
from pulse.state.ledger import RunLedger
from tests.orch_helpers import build_raw_reviews, make_config, seeded_registry


@pytest.fixture(autouse=True)
def _fresh_mcp():
    reset_shared()
    yield
    reset_shared()


def test_metrics_emitted(tmp_path):
    # E7.11 — all required metrics present after a run.
    with RunLedger(tmp_path / "l.db") as ledger:
        summary = AgentCore(make_config(), ledger, seeded_registry(build_raw_reviews())).run("groww", "2026-W26")
    m = summary.metrics
    for key in ("reviews_in", "clusters", "themes", "quotes_validated", "quotes_dropped",
                "tokens", "cost_usd", "latency_seconds"):
        assert key in m
    assert m["reviews_in"] == 18 and m["latency_seconds"] >= 0


def test_budget_halt_recorded(tmp_path):
    # E7.7 / X7.8 — a tiny token cap halts summarization gracefully; run still completes.
    config = make_config(max_tokens=1)
    with RunLedger(tmp_path / "l.db") as ledger:
        summary = AgentCore(config, ledger, seeded_registry(build_raw_reviews())).run("groww", "2026-W26")
    assert summary.status == "COMPLETED"
    assert summary.metrics["budget_halted"] is True
    assert summary.metrics["themes"] == 0


def test_audit_returns_full_record(tmp_path):
    # E7.10 — audit answers "what was sent when, for which week?".
    with RunLedger(tmp_path / "l.db") as ledger:
        AgentCore(make_config(), ledger, seeded_registry(build_raw_reviews())).run("groww", "2026-W26")

    args = type("A", (), {"product": "groww", "week": "2026-W26", "ledger": str(tmp_path / "l.db")})
    out = audit_command(args)
    assert out["found"] is True and out["status"] == "COMPLETED"
    assert out["doc_id"] == "doc-groww"
    assert out["section_anchor"] == "pulse-groww-2026-W26"
    assert out["heading_id"] and out["deep_link"] and out["message_id"]
    assert out["email_status"] == "draft"
    assert "metrics" in out and out["started_at"] is not None


def test_audit_no_run(tmp_path):
    # X7.12 — a week that never ran returns a clear "no run", not an error.
    args = type("A", (), {"product": "groww", "week": "2026-W26", "ledger": str(tmp_path / "empty.db")})
    out = audit_command(args)
    assert out["found"] is False and out["status"] == "NO_RUN"
