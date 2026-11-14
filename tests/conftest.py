from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from habits.core.clock import ManualClock
from habits.core.service import HabitService
from habits.db.connection import connect
from habits.db.repo import SqliteRepository

TZ = ZoneInfo("America/New_York")


def at(y: int, mo: int, d: int, h: int = 12, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=TZ)


@pytest.fixture
def clock() -> ManualClock:
    # Saturday 14 Nov 2026, midday.
    return ManualClock(at(2026, 11, 14, 12))


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    c = connect(":memory:")
    yield c
    c.close()


@pytest.fixture
def repo(conn: sqlite3.Connection) -> SqliteRepository:
    return SqliteRepository(conn)


@pytest.fixture
def service(repo: SqliteRepository, clock: ManualClock) -> HabitService:
    return HabitService(repo, clock)
