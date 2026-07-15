"""E6.3/E6.4/E6.7/E6.9 + X6.1 — full agent run delivery & idempotency (mock transport)."""

import pytest

from pulse.agent.core import AgentCore
from pulse.config import Config, Product, ProductRegistry, Settings
from pulse.delivery.mock_mcp import reset_shared, shared_docs_client, shared_gmail_client
from pulse.state.ledger import RunLedger

ANCHOR = "pulse-groww-2026-W26"
DOC_ID = "doc-groww"


def _config(email_mode="draft"):
    settings = Settings(email_mode=email_mode)  # transport defaults to "mock"
    registry = ProductRegistry(
        products=[
            Product(id="groww", name="Groww", app_store_id="1", play_package="com.groww",
                    doc_id=DOC_ID, recipients=["product-pulse@example.com"])
        ]
    )
    return Config(settings=settings, registry=registry)


@pytest.fixture(autouse=True)
def _fresh_mcp():
    reset_shared()
    yield
    reset_shared()


def test_full_run_delivers_and_records_ledger(tmp_path):
    config = _config()
    with RunLedger(tmp_path / "ledger.db") as ledger:
        agent = AgentCore(config=config, ledger=ledger)
        summary = agent.run("groww", "2026-W26", offline=True)
        assert summary.status == "COMPLETED"

        rec = ledger.get("groww", "2026-W26")
        # E6.9 — delivery identifiers recorded.
        assert rec.doc_id == DOC_ID
        assert rec.section_anchor == ANCHOR
        assert rec.heading_id
        assert rec.deep_link == f"https://docs.google.com/document/d/{DOC_ID}/edit#heading={rec.heading_id}"
        assert rec.email_status == "draft" and rec.message_id

    assert shared_docs_client().section_count(DOC_ID, ANCHOR) == 1
    assert len(shared_gmail_client().drafts) == 1


def test_rerun_is_idempotent(tmp_path):
    config = _config()
    with RunLedger(tmp_path / "ledger.db") as ledger:
        agent = AgentCore(config=config, ledger=ledger)
        agent.run("groww", "2026-W26", offline=True)
        again = agent.run("groww", "2026-W26", offline=True)
        assert again.status == "SKIPPED_ALREADY_COMPLETED"

    # X6.1 / E6.3 / E6.7 — no duplicate section, no duplicate draft.
    assert shared_docs_client().section_count(DOC_ID, ANCHOR) == 1
    assert len(shared_gmail_client().drafts) == 1


def test_force_replaces_section_without_duplicate(tmp_path):
    config = _config()
    with RunLedger(tmp_path / "ledger.db") as ledger:
        agent = AgentCore(config=config, ledger=ledger)
        agent.run("groww", "2026-W26", offline=True)
        forced = agent.run("groww", "2026-W26", offline=True, force=True)
        assert forced.status == "COMPLETED"

    # E6.4 — exactly one section remains after force replace.
    assert shared_docs_client().section_count(DOC_ID, ANCHOR) == 1


def test_dry_run_skips_mcp_writes(tmp_path):
    config = _config()
    with RunLedger(tmp_path / "ledger.db") as ledger:
        agent = AgentCore(config=config, ledger=ledger)
        summary = agent.run("groww", "2026-W26", offline=True, dry_run=True)
        assert summary.status == "COMPLETED"
        rec = ledger.get("groww", "2026-W26")
        assert rec.section_anchor == ANCHOR  # render still computes the anchor
        assert rec.email_status == "none"    # no MCP delivery happened

    # No MCP writes occurred.
    assert shared_docs_client().docs == {} or shared_docs_client().section_count(DOC_ID, ANCHOR) == 0
    assert len(shared_gmail_client().drafts) == 0
