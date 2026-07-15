"""Run ledger — idempotency + audit (architecture §8.2).

Backed by SQLite (stdlib). The primary key is (product_id, iso_week). The ledger answers
"what was sent when, for which week?" and enforces single-run acquisition so re-runs do not
duplicate work (idempotency short-circuit lives in the agent core, gated by this store).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pulse.models import RunRecord


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunInProgressError(RuntimeError):
    """Raised when a non-stale RUNNING record already holds (product, iso_week) (X0.9)."""


class LedgerCorruptionError(RuntimeError):
    """Raised when a stored record cannot be parsed (X0.8)."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    product_id   TEXT NOT NULL,
    iso_week     TEXT NOT NULL,
    status       TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    record_json  TEXT NOT NULL,
    PRIMARY KEY (product_id, iso_week)
);
"""


class RunLedger:
    def __init__(self, db_path: str | Path = ".pulse/ledger.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.execute(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "RunLedger":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get(self, product_id: str, iso_week: str) -> RunRecord | None:
        row = self._conn.execute(
            "SELECT record_json FROM runs WHERE product_id=? AND iso_week=?",
            (product_id, iso_week),
        ).fetchone()
        if row is None:
            return None
        try:
            return RunRecord.model_validate_json(row[0])
        except Exception as exc:  # noqa: BLE001 - surface corruption clearly
            raise LedgerCorruptionError(
                f"Corrupted ledger record for {product_id} {iso_week}: {exc}"
            ) from exc

    def upsert(self, record: RunRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO runs (product_id, iso_week, status, started_at, record_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(product_id, iso_week) DO UPDATE SET
                status=excluded.status,
                started_at=excluded.started_at,
                record_json=excluded.record_json
            """,
            (
                record.product_id,
                record.iso_week,
                record.status,
                record.started_at.isoformat(),
                record.model_dump_json(),
            ),
        )

    def try_start(
        self,
        product_id: str,
        iso_week: str,
        *,
        force: bool = False,
        stale_after_minutes: int = 120,
    ) -> tuple[RunRecord, bool]:
        """Acquire a run slot.

        Returns ``(record, already_completed)``.
        - If a COMPLETED record exists and ``force`` is False, returns it with True.
        - If a non-stale RUNNING record exists (and not forced), raises RunInProgressError.
        - Otherwise creates/overwrites a fresh RUNNING record and returns it with False.
        """
        existing = self.get(product_id, iso_week)
        now = utcnow()

        if existing is not None and not force:
            if existing.status == "COMPLETED":
                return existing, True
            if existing.status == "RUNNING":
                started = existing.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                if now - started < timedelta(minutes=stale_after_minutes):
                    raise RunInProgressError(
                        f"A run for {product_id} {iso_week} is already in progress "
                        f"(started {started.isoformat()})."
                    )
                # else: stale RUNNING — safe to reclaim (X0.10).

        record = RunRecord(
            run_id=str(uuid.uuid4()),
            product_id=product_id,
            iso_week=iso_week,
            status="RUNNING",
            started_at=now,
            metrics={},
        )
        self.upsert(record)
        return record, False

    def list_runs(self) -> list[RunRecord]:
        rows = self._conn.execute(
            "SELECT record_json FROM runs ORDER BY started_at"
        ).fetchall()
        return [RunRecord.model_validate_json(r[0]) for r in rows]
