from __future__ import annotations

from datetime import date, timedelta

import pytest

from habits.core import stats
from habits.core.clock import ManualClock
from habits.core.models import DayTotal, TodayRow
from habits.core.service import HabitService


@pytest.mark.parametrize(
    ("done", "total", "level"),
    [
        (0, 0, 0),
        (0, 5, 0),
        (1, 8, 1),
        (2, 8, 1),
        (3, 8, 2),
        (4, 8, 2),
        (5, 8, 3),
        (7, 8, 3),
        (8, 8, 4),
    ],
)
def test_shade_level(done: int, total: int, level: int) -> None:
    assert stats.shade_level(done, total) == level


def test_progress_modes() -> None:
    rows = [
        TodayRow("group", "g", "Water", "a", done=3, total=8),
        TodayRow("habit", "h1", "Read", "b", done=1, total=1),
        TodayRow("habit", "h2", "Run", "c", done=0, total=1),
    ]
    assert stats.progress(rows) == (4, 10)
    assert stats.progress(rows, "rows") == (1, 3)


def test_heatmap_grid_shape() -> None:
    today = date(2026, 11, 14)  # Saturday
    grid = stats.heatmap_grid({}, today, weeks=12)
    assert len(grid) == 12 and all(len(c) == 7 for c in grid)
    first = grid[0][0]
    assert first is not None and date.fromisoformat(first.day).weekday() == 0
    assert grid[-1][5] is not None and grid[-1][5].day == "2026-11-14"
    assert grid[-1][6] is None  # Sunday is in the future
    assert first.ratio is None  # nothing active: blank


def test_review_view_partial_and_pre_creation_days(
    service: HabitService, clock: ManualClock
) -> None:
    clock.advance(timedelta(days=-2))  # Thursday 12 Nov
    gid = service.add("Water x8")
    hid = service.add("Read")
    assert gid and hid
    for _ in range(3):
        service.tick_group(gid)
    clock.advance(timedelta(days=1))  # Friday
    service.toggle_habit(hid)
    for _ in range(8):
        service.tick_group(gid)
    clock.advance(timedelta(days=1))  # Saturday

    review = service.review_view()
    cells = {c.day: c for col in review.heatmap for c in col if c is not None}
    assert cells["2026-11-11"].ratio is None  # before anything existed: blank
    assert (cells["2026-11-12"].done, cells["2026-11-12"].total) == (3, 9)
    assert cells["2026-11-12"].level == 2  # partial day is visibly something
    assert cells["2026-11-13"].level == 4
    assert (cells["2026-11-14"].done, cells["2026-11-14"].total) == (0, 9)

    assert review.yesterday.day == "2026-11-13"
    assert (review.yesterday.done, review.yesterday.total) == (9, 9)
    assert [t.day for t in review.week] == [
        (date(2026, 11, 8) + timedelta(days=i)).isoformat() for i in range(7)
    ]
    assert review.week[-2] == DayTotal("2026-11-13", 9, 9)
    assert review.showed_up_days == 2
    assert review.window_days == 14


def test_review_uses_each_days_denominator(service: HabitService, clock: ManualClock) -> None:
    gid = service.add("Water x4")
    assert gid
    clock.advance(timedelta(days=1))
    service.grow_group(gid)
    clock.advance(timedelta(days=1))
    totals = {t.day: t.total for t in service.review_view().week}
    assert totals["2026-11-13"] == 0
    assert totals["2026-11-14"] == 4
    assert totals["2026-11-15"] == 5
    assert totals["2026-11-16"] == 5
