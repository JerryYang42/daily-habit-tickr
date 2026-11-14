from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from habits.core.clock import (
    ManualClock,
    SystemClock,
    logical_day,
    next_boundary,
    seconds_until_boundary,
)

NY = ZoneInfo("America/New_York")
LON = ZoneInfo("Europe/London")


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # 04:59 vs 05:00
        (datetime(2026, 11, 17, 4, 59, tzinfo=NY), date(2026, 11, 16)),
        (datetime(2026, 11, 17, 5, 0, tzinfo=NY), date(2026, 11, 17)),
        (datetime(2026, 11, 17, 4, 59, 59, 999999, tzinfo=NY), date(2026, 11, 16)),
        # midnight and the small hours belong to the previous day
        (datetime(2026, 11, 17, 0, 0, tzinfo=NY), date(2026, 11, 16)),
        (datetime(2026, 11, 17, 2, 0, tzinfo=NY), date(2026, 11, 16)),
        (datetime(2026, 11, 16, 23, 59, tzinfo=NY), date(2026, 11, 16)),
        # month and year boundaries
        (datetime(2026, 12, 1, 3, 0, tzinfo=NY), date(2026, 11, 30)),
        (datetime(2027, 1, 1, 4, 0, tzinfo=NY), date(2026, 12, 31)),
        (datetime(2027, 1, 1, 5, 0, tzinfo=NY), date(2027, 1, 1)),
        (datetime(2028, 3, 1, 1, 0, tzinfo=NY), date(2028, 2, 29)),  # leap day
        # DST spring forward (NY: 2026-03-08 02:00 -> 03:00)
        (datetime(2026, 3, 8, 1, 59, tzinfo=NY), date(2026, 3, 7)),
        (datetime(2026, 3, 8, 3, 0, tzinfo=NY), date(2026, 3, 7)),
        (datetime(2026, 3, 8, 4, 59, tzinfo=NY), date(2026, 3, 7)),
        (datetime(2026, 3, 8, 5, 0, tzinfo=NY), date(2026, 3, 8)),
        # DST fall back (NY: 2026-11-01 02:00 -> 01:00, 01:30 happens twice)
        (datetime(2026, 11, 1, 1, 30, fold=0, tzinfo=NY), date(2026, 10, 31)),
        (datetime(2026, 11, 1, 1, 30, fold=1, tzinfo=NY), date(2026, 10, 31)),
        (datetime(2026, 11, 1, 4, 59, tzinfo=NY), date(2026, 10, 31)),
        (datetime(2026, 11, 1, 5, 0, tzinfo=NY), date(2026, 11, 1)),
        # London DST (2026-03-29 01:00 -> 02:00)
        (datetime(2026, 3, 29, 4, 30, tzinfo=LON), date(2026, 3, 28)),
        (datetime(2026, 3, 29, 5, 30, tzinfo=LON), date(2026, 3, 29)),
    ],
)
def test_logical_day(now: datetime, expected: date) -> None:
    assert logical_day(now) == expected


@pytest.mark.parametrize(
    ("hour", "now", "expected"),
    [
        (0, datetime(2026, 11, 17, 0, 0, tzinfo=NY), date(2026, 11, 17)),
        (0, datetime(2026, 11, 16, 23, 59, tzinfo=NY), date(2026, 11, 16)),
        (4, datetime(2026, 11, 17, 4, 0, tzinfo=NY), date(2026, 11, 17)),
        (4, datetime(2026, 11, 17, 3, 59, tzinfo=NY), date(2026, 11, 16)),
    ],
)
def test_logical_day_custom_start(hour: int, now: datetime, expected: date) -> None:
    assert logical_day(now, hour) == expected


def test_logical_day_uses_wall_clock_not_utc() -> None:
    # 06:00 in Tokyo is 21:00 UTC the previous day; the local wall clock wins.
    tokyo = datetime(2026, 11, 17, 6, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert logical_day(tokyo) == date(2026, 11, 17)
    assert logical_day(tokyo.astimezone(UTC)) == date(2026, 11, 16)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 17, 2, 0, tzinfo=NY), datetime(2026, 11, 17, 5, 0, tzinfo=NY)),
        (datetime(2026, 11, 17, 5, 0, tzinfo=NY), datetime(2026, 11, 18, 5, 0, tzinfo=NY)),
        (datetime(2026, 11, 17, 23, 0, tzinfo=NY), datetime(2026, 11, 18, 5, 0, tzinfo=NY)),
        (datetime(2026, 12, 31, 12, 0, tzinfo=NY), datetime(2027, 1, 1, 5, 0, tzinfo=NY)),
    ],
)
def test_next_boundary(now: datetime, expected: datetime) -> None:
    assert next_boundary(now) == expected


def test_seconds_until_boundary_across_spring_forward() -> None:
    # 01:00 EST -> 05:00 EDT is only 3 real hours.
    now = datetime(2026, 3, 8, 1, 0, tzinfo=NY)
    assert seconds_until_boundary(now) == pytest.approx(3 * 3600)


def test_seconds_until_boundary_is_positive() -> None:
    now = datetime(2026, 11, 17, 4, 59, 59, tzinfo=NY)
    assert seconds_until_boundary(now) == pytest.approx(1)


def test_manual_clock() -> None:
    c = ManualClock(datetime(2026, 1, 1, tzinfo=UTC))
    c.advance(timedelta(hours=2))
    assert c.now() == datetime(2026, 1, 1, 2, tzinfo=UTC)
    with pytest.raises(ValueError):
        ManualClock(datetime(2026, 1, 1))


def test_system_clock_is_aware() -> None:
    assert SystemClock().now().tzinfo is not None
    fixed = timezone(timedelta(hours=9))
    assert SystemClock(fixed).now().utcoffset() == timedelta(hours=9)
