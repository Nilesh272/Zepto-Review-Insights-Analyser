"""E7.1/E7.2/E7.6/E7.8 — full end-to-end agent run via mock MCP (seeded sources)."""

import pytest

from pulse.agent.core import AgentCore
from pulse.delivery.mock_mcp import reset_shared, shared_docs_client, shared_gmail_client
from pulse.state.ledger import RunLedger
from tests.orch_helpers import build_raw_reviews, make_config, seeded_registry


@pytest.fixture(autouse=True)
def _fresh_mcp():
    reset_shared()
    yield
    reset_shared()


def _agent(ledger):
    return AgentCore(config=make_config(), ledger=ledger, registry=seeded_registry(build_raw_reviews()))


def test_e2e_grounded_pulse_delivered(tmp_path):
    # E7.1 — themes with validated quotes appended to the Doc; email drafted via MCP.
    with RunLedger(tmp_path / "l.db") as ledger:
        summary = _agent(ledger).run("groww", "2026-W26")
        assert summary.status == "COMPLETED"
        assert summary.metrics["reviews_in"] == 18
        assert summary.metrics["clusters"] >= 1
        assert summary.metrics["themes"] >= 1
        assert summary.metrics["quotes_validated"] >= 1
        assert summary.email_status == "draft"
        assert summary.deep_link and "#heading=" in summary.deep_link

    assert shared_docs_client().section_count("doc-groww", "pulse-groww-2026-W26") == 1
    assert len(shared_gmail_client().drafts) == 1
    # The appended Doc carries a validated quote verbatim.
    doc = shared_docs_client().docs["doc-groww"]["sections"]["pulse-groww-2026-W26"]
    text = "".join(r["insertText"]["text"] for r in doc["requests"] if "insertText" in r)
    assert "trading" in text.lower()


def test_e2e_idempotent_rerun(tmp_path):
    # E7.2 — re-run is a no-op; no duplicate section/draft.
    with RunLedger(tmp_path / "l.db") as ledger:
        _agent(ledger).run("groww", "2026-W26")
        again = _agent(ledger).run("groww", "2026-W26")
        assert again.status == "SKIPPED_ALREADY_COMPLETED"
    assert shared_docs_client().section_count("doc-groww", "pulse-groww-2026-W26") == 1
    assert len(shared_gmail_client().drafts) == 1


def test_backfill_historic_week(tmp_path):
    # E7.6 — an older ISO week produces its own anchored section.
    with RunLedger(tmp_path / "l.db") as ledger:
        summary = _agent(ledger).run("groww", "2026-W21")
        assert summary.status == "COMPLETED"
        assert summary.section_anchor == "pulse-groww-2026-W21"
    assert shared_docs_client().section_count("doc-groww", "pulse-groww-2026-W21") == 1


def test_dry_run_skips_mcp(tmp_path):
    # E7.8 — full loop, no MCP writes.
    with RunLedger(tmp_path / "l.db") as ledger:
        summary = _agent(ledger).run("groww", "2026-W26", dry_run=True)
        assert summary.status == "COMPLETED"
        assert summary.email_status == "none"
    assert len(shared_gmail_client().drafts) == 0
