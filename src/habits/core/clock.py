"""Clocks and the logical-day (5am) rule."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Protocol

DEFAULT_DAY_START_HOUR = 5


class Clock(Protocol):
    """Source of the current time. Must return a timezone-aware datetime."""

    def now(self) -> datetime: ...


class SystemClock:
    """The real wall clock, in the local zone or an explicit override."""

    def __init__(self, tz: tzinfo | None = None) -> None:
        self._tz = tz

    def now(self) -> datetime:
        if self._tz is not None:
            return datetime.now(self._tz)
        return datetime.now().astimezone()


class ManualClock:
    """A clock you set by hand. Used by tests and demos."""

    def __init__(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("ManualClock needs an aware datetime")
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("ManualClock needs an aware datetime")
        self._now = now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


def logical_day(now_local: datetime, day_start_hour: int = DEFAULT_DAY_START_HOUR) -> date:
    """The day a wall-clock moment belongs to, where days start at `day_start_hour`.

    Uses wall-clock arithmetic (tz stripped) so DST shifts never move the boundary.
    """
    wall = now_local.replace(tzinfo=None)
    return (wall - timedelta(hours=day_start_hour)).date()


def next_boundary(now_local: datetime, day_start_hour: int = DEFAULT_DAY_START_HOUR) -> datetime:
    """The next wall-clock moment at which the logical day changes."""
    following = logical_day(now_local, day_start_hour) + timedelta(days=1)
    return datetime.combine(following, time(hour=day_start_hour), tzinfo=now_local.tzinfo)


def seconds_until_boundary(
    now_local: datetime, day_start_hour: int = DEFAULT_DAY_START_HOUR
) -> float:
    """Seconds until the next rollover (never negative)."""
    # Compare in UTC: same-zone aware subtraction would use wall-clock time and be off by DST.
    delta = next_boundary(now_local, day_start_hour).astimezone(UTC) - now_local.astimezone(UTC)
    return max(delta.total_seconds(), 0.0)


def day_key(d: date) -> str:
    """Storage form of a logical day: YYYY-MM-DD."""
    return d.isoformat()
