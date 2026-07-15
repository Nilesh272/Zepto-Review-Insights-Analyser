"""E0.6 ISO-week parsing; X0.1/X0.2 edge cases."""

import pytest

from pulse.utils.isoweek import IsoWeek, IsoWeekError, parse_iso_week


def test_parse_valid_weeks():
    assert parse_iso_week("2026-W01") == IsoWeek(2026, 1)
    assert parse_iso_week("2026-W26") == IsoWeek(2026, 26)
    assert str(parse_iso_week("2026-W05")) == "2026-W05"


def test_w53_valid_in_53_week_year():
    # 2026 is a 53-week ISO year.
    assert parse_iso_week("2026-W53") == IsoWeek(2026, 53)


def test_w53_invalid_in_52_week_year():
    # 2025 has only 52 ISO weeks (X0.2).
    with pytest.raises(IsoWeekError):
        parse_iso_week("2025-W53")


@pytest.mark.parametrize("bad", ["2026-W00", "2026-W54", "2026-13", "2026W26", "garbage", ""])
def test_malformed_rejected(bad):
    # X0.1
    with pytest.raises(IsoWeekError):
        parse_iso_week(bad)


def test_week_boundaries_utc():
    wk = parse_iso_week("2026-W26")
    assert wk.monday().weekday() == 0
    assert wk.sunday().weekday() == 6
    assert wk.monday().tzinfo is not None
