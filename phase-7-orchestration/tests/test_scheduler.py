"""E7.3/E7.4 + X7.1/X7.2/X7.5/X7.6 — weekly scheduling, failure isolation, ISO-week math."""

from datetime import datetime, timezone

import pytest

from pulse.agent.core import AgentCore
from pulse.delivery.mock_mcp import reset_shared, shared_docs_client
from pulse.scheduler import IST, just_completed_iso_week, run_weekly
from pulse.state.ledger import RunLedger
from tests.orch_helpers import build_raw_reviews, multi_product_config, seeded_registry


@pytest.fixture(autouse=True)
def _fresh_mcp():
    reset_shared()
    yield
    reset_shared()


def test_just_completed_week_basic():
    # Monday 2026-06-29 IST is in 2026-W27 -> just-completed is 2026-W26.
    now = datetime(2026, 6, 29, 9, 0, tzinfo=IST)
    assert str(just_completed_iso_week(now)) == "2026-W26"


def test_just_completed_week_year_boundary():
    # X7.6 — early January maps back into the prior ISO year correctly.
    now = datetime(2026, 1, 2, 9, 0, tzinfo=IST)  # 2026-W01
    assert str(just_completed_iso_week(now)) == "2025-W52"


def test_ist_offset_changes_week_near_midnight():
    # X7.5 — a UTC instant late Sunday is already Monday IST (+5:30), advancing the week.
    sun_utc = datetime(2026, 6, 28, 20, 0, tzinfo=timezone.utc)  # Mon 01:30 IST -> 2026-W27
    assert str(just_completed_iso_week(sun_utc)) == "2026-W26"


def _run_weekly(ledger, config_ids, *, run_ids=None, **kw):
    config = multi_product_config(config_ids)
    agent_registry = seeded_registry(build_raw_reviews())
    # run_weekly builds its own AgentCore; inject the seeded registry by monkeypatching.
    import pulse.scheduler as sched

    orig = sched.AgentCore

    def _factory(config, ledger):
        return AgentCore(config=config, ledger=ledger, registry=agent_registry)

    sched.AgentCore = _factory
    try:
        return run_weekly(config, ledger, iso_week="2026-W26", product_ids=run_ids, **kw)
    finally:
        sched.AgentCore = orig


def test_weekly_runs_all_products(tmp_path):
    # E7.3 — every configured product processed for the target week.
    with RunLedger(tmp_path / "l.db") as ledger:
        summaries = _run_weekly(ledger, ["groww", "kuvera", "indmoney"])
    assert len(summaries) == 3
    assert all(s.status == "COMPLETED" for s in summaries)
    assert {s.product_id for s in summaries} == {"groww", "kuvera", "indmoney"}


def test_failure_isolation(tmp_path):
    # E7.4 / X7.1 — an unknown product fails in isolation; others still complete.
    with RunLedger(tmp_path / "l.db") as ledger:
        summaries = _run_weekly(
            ledger, ["groww", "kuvera"], run_ids=["groww", "does_not_exist", "kuvera"]
        )
    by_id = {s.product_id: s.status for s in summaries}
    assert by_id["does_not_exist"] == "FAILED"
    assert by_id["groww"] == "COMPLETED" and by_id["kuvera"] == "COMPLETED"


def test_retrigger_is_idempotent(tmp_path):
    # X7.2 — scheduler firing twice does not duplicate sections.
    with RunLedger(tmp_path / "l.db") as ledger:
        _run_weekly(ledger, ["groww"])
        second = _run_weekly(ledger, ["groww"])
    assert second[0].status == "SKIPPED_ALREADY_COMPLETED"
    assert shared_docs_client().section_count("doc-groww", "pulse-groww-2026-W26") == 1
