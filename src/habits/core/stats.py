"""Positive-only stats: totals, heatmap shading, progress.

There are deliberately no streaks and no "missed" counts here.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from typing import Literal

from habits.core.models import DayTotal, Habit, HabitGroup, HeatmapCell, TodayRow

ProgressMode = Literal["ticks", "rows"]

# "ticks": every box counts (Water 3/8 contributes 3 of 8).
# "rows":  a group counts once, and only when complete.
PROGRESS_MODE: ProgressMode = "ticks"


def progress(rows: Iterable[TodayRow], mode: ProgressMode = PROGRESS_MODE) -> tuple[int, int]:
    """(done, total) for the progress line."""
    rows = list(rows)
    if mode == "rows":
        return sum(1 for r in rows if r.complete), len(rows)
    return sum(r.done for r in rows), sum(r.total for r in rows)


def habit_active_on(habit: Habit, groups: Mapping[str, HabitGroup], day: str) -> bool:
    if not habit.active_on(day):
        return False
    if habit.group_id is None:
        return True
    group = groups.get(habit.group_id)
    return group is not None and group.active_on(day)


def day_totals(
    habits: Sequence[Habit],
    groups: Mapping[str, HabitGroup],
    done: set[tuple[str, str]],
    days: Iterable[str],
) -> list[DayTotal]:
    """Done ticks over active habits for each day. `done` holds (habit_id, day) pairs."""
    out: list[DayTotal] = []
    for day in days:
        active = [h for h in habits if habit_active_on(h, groups, day)]
        n_done = sum(1 for h in active if (h.id, day) in done)
        out.append(DayTotal(day=day, done=n_done, total=len(active)))
    return out


def shade_level(done: int, total: int) -> int:
    """0 for nothing yet, then 1..4 by share. Partial days are always visibly something."""
    if total <= 0 or done <= 0:
        return 0
    ratio = done / total
    if ratio <= 0.25:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio < 1:
        return 3
    return 4


def heatmap_start(today: date, weeks: int) -> date:
    """Monday of the first column of a `weeks`-wide grid ending in today's week."""
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(weeks=weeks - 1)


def heatmap_grid(
    totals: Mapping[str, DayTotal], today: date, weeks: int
) -> list[list[HeatmapCell | None]]:
    """Columns of 7 cells (Mon..Sun). Days after today are None."""
    start = heatmap_start(today, weeks)
    grid: list[list[HeatmapCell | None]] = []
    for w in range(weeks):
        column: list[HeatmapCell | None] = []
        for d in range(7):
            day = start + timedelta(weeks=w, days=d)
            if day > today:
                column.append(None)
                continue
            key = day.isoformat()
            t = totals.get(key, DayTotal(key, 0, 0))
            column.append(
                HeatmapCell(
                    day=key,
                    done=t.done,
                    total=t.total,
                    level=shade_level(t.done, t.total),
                    ratio=(t.done / t.total) if t.total else None,
                )
            )
        grid.append(column)
    return grid


def showed_up_days(totals: Iterable[DayTotal]) -> int:
    """How many days had at least one tick."""
    return sum(1 for t in totals if t.done > 0)
