"""ISO-8601 week parsing/formatting (architecture §9).

Internally the agent reasons in UTC; ISO weeks identify a run via (iso_year, iso_week).
Validation uses the real ISO calendar so e.g. W53 is rejected in 52-week years.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

_ISO_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


class IsoWeekError(ValueError):
    """Raised for malformed or calendar-invalid ISO weeks."""


@dataclass(frozen=True)
class IsoWeek:
    year: int
    week: int

    def __str__(self) -> str:
        return f"{self.year}-W{self.week:02d}"

    @property
    def label(self) -> str:
        return str(self)

    def monday(self) -> datetime:
        """UTC midnight of the Monday of this ISO week."""
        d = date.fromisocalendar(self.year, self.week, 1)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

    def sunday(self) -> datetime:
        d = date.fromisocalendar(self.year, self.week, 7)
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def parse_iso_week(value: str) -> IsoWeek:
    """Parse 'YYYY-Www' into an IsoWeek, validating against the ISO calendar.

    Rejects malformed strings (X0.1) and calendar-invalid weeks such as W00/W54, or W53 in a
    year that only has 52 ISO weeks (X0.2).
    """
    if not isinstance(value, str):
        raise IsoWeekError(f"ISO week must be a string, got {type(value).__name__}")
    m = _ISO_WEEK_RE.match(value.strip())
    if not m:
        raise IsoWeekError(
            f"Malformed ISO week {value!r}; expected format 'YYYY-Www' (e.g. 2026-W26)"
        )
    year, week = int(m.group(1)), int(m.group(2))
    if week < 1:
        raise IsoWeekError(f"Invalid ISO week number {week:02d} in {value!r} (must be >= 01)")
    try:
        # Raises ValueError if the (year, week) does not exist in the ISO calendar.
        date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise IsoWeekError(
            f"{value!r} is not a valid ISO week for year {year}: {exc}"
        ) from exc
    return IsoWeek(year=year, week=week)


def current_iso_week(now: datetime | None = None) -> IsoWeek:
    now = now or datetime.now(timezone.utc)
    iso = now.isocalendar()
    return IsoWeek(year=iso.year, week=iso.week)
