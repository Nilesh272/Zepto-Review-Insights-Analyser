"""E0.9 dry-run smoke + E0.5 end-to-end idempotency; X0.1/X0.3 fail-fast via core."""

from pathlib import Path

import pytest

from pulse.agent.core import AgentCore
from pulse.agent.tools import DEFAULT_PLAN
from pulse.config import load_config
from pulse.state.ledger import RunLedger
from pulse.utils.isoweek import IsoWeekError

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _agent(tmp_path) -> tuple[AgentCore, RunLedger]:
    cfg = load_config(CONFIG_DIR)
    ledger = RunLedger(tmp_path / "ledger.db")
    return AgentCore(config=cfg, ledger=ledger), ledger


def test_dry_run_completes_and_records(tmp_path):
    agent, ledger = _agent(tmp_path)
    summary = agent.run("groww", "2026-W26", dry_run=True)

    assert summary.status == "COMPLETED"
    assert summary.steps == DEFAULT_PLAN
    assert summary.section_anchor == "pulse-groww-2026-W26"

    rec = ledger.get("groww", "2026-W26")
    assert rec.status == "COMPLETED"
    assert rec.metrics["dry_run"] is True
    ledger.close()


def test_rerun_is_idempotent(tmp_path):
    agent, ledger = _agent(tmp_path)
    agent.run("groww", "2026-W26", dry_run=True)
    second = agent.run("groww", "2026-W26", dry_run=True)
    assert second.status == "SKIPPED_ALREADY_COMPLETED"
    ledger.close()


def test_force_reruns(tmp_path):
    agent, ledger = _agent(tmp_path)
    first = agent.run("groww", "2026-W26", dry_run=True)
    forced = agent.run("groww", "2026-W26", dry_run=True, force=True)
    assert forced.status == "COMPLETED"
    assert forced.run_id != first.run_id
    ledger.close()


def test_bad_week_fails_fast(tmp_path):
    agent, ledger = _agent(tmp_path)
    with pytest.raises(IsoWeekError):
        agent.run("groww", "2026-W54", dry_run=True)
    ledger.close()


def test_unknown_product_fails_fast(tmp_path):
    agent, ledger = _agent(tmp_path)
    with pytest.raises(KeyError):
        agent.run("nope", "2026-W26", dry_run=True)
    ledger.close()
