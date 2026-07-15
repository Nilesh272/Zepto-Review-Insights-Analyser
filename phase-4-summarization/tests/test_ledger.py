"""E0.4 ledger lifecycle, E0.5 idempotency; X0.7/X0.9/X0.10 edge cases."""

from datetime import timedelta

import pytest

from pulse.state.ledger import RunInProgressError, RunLedger, utcnow


def test_ledger_autocreates_and_lifecycle(tmp_path):
    # E0.4 + X0.7 (file auto-created)
    db = tmp_path / "nested" / "ledger.db"
    with RunLedger(db) as ledger:
        assert db.exists()
        rec, already = ledger.try_start("groww", "2026-W26")
        assert already is False and rec.status == "RUNNING"

        rec.status = "COMPLETED"
        rec.finished_at = utcnow()
        ledger.upsert(rec)

        fetched = ledger.get("groww", "2026-W26")
        assert fetched.status == "COMPLETED"


def test_idempotency_short_circuit(tmp_path):
    # E0.5 — completed run is returned as already_completed.
    with RunLedger(tmp_path / "l.db") as ledger:
        rec, _ = ledger.try_start("groww", "2026-W26")
        rec.status = "COMPLETED"
        ledger.upsert(rec)

        again, already = ledger.try_start("groww", "2026-W26")
        assert already is True
        assert again.run_id == rec.run_id


def test_running_lock_blocks_second_start(tmp_path):
    # X0.9 — a fresh RUNNING record blocks another start.
    with RunLedger(tmp_path / "l.db") as ledger:
        ledger.try_start("groww", "2026-W26")
        with pytest.raises(RunInProgressError):
            ledger.try_start("groww", "2026-W26")


def test_stale_running_can_be_reclaimed(tmp_path):
    # X0.10 — a RUNNING record older than the stale window is reclaimable.
    with RunLedger(tmp_path / "l.db") as ledger:
        rec, _ = ledger.try_start("groww", "2026-W26")
        rec.started_at = utcnow() - timedelta(hours=5)
        ledger.upsert(rec)

        new_rec, already = ledger.try_start("groww", "2026-W26", stale_after_minutes=120)
        assert already is False
        assert new_rec.run_id != rec.run_id


def test_force_overrides_completed(tmp_path):
    with RunLedger(tmp_path / "l.db") as ledger:
        rec, _ = ledger.try_start("groww", "2026-W26")
        rec.status = "COMPLETED"
        ledger.upsert(rec)

        new_rec, already = ledger.try_start("groww", "2026-W26", force=True)
        assert already is False and new_rec.status == "RUNNING"
