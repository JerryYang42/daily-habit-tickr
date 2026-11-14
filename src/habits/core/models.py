"""Domain dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CompletionState = Literal["done", "cleared"]
RowKind = Literal["habit", "group"]

MIN_GROUP_SIZE = 2
MAX_GROUP_SIZE = 50


def _active_on(created_day: str, archived_day: str | None, day: str) -> bool:
    return created_day <= day and (archived_day is None or archived_day > day)


@dataclass(frozen=True, slots=True)
class Habit:
    id: str
    name: str
    sort_key: str
    created_day: str
    updated_at: str
    group_id: str | None = None
    group_pos: int | None = None
    archived_day: str | None = None

    def active_on(self, day: str) -> bool:
        return _active_on(self.created_day, self.archived_day, day)


@dataclass(frozen=True, slots=True)
class HabitGroup:
    id: str
    name: str
    sort_key: str
    created_day: str
    updated_at: str
    emoji: str | None = None
    archived_day: str | None = None

    def active_on(self, day: str) -> bool:
        return _active_on(self.created_day, self.archived_day, day)


@dataclass(frozen=True, slots=True)
class Completion:
    habit_id: str
    day: str
    state: CompletionState
    updated_at: str
    device_id: str


@dataclass(frozen=True, slots=True)
class GroupProgress:
    done: int
    total: int

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.done >= self.total


@dataclass(frozen=True, slots=True)
class TodayRow:
    """One line in a day list: a plain habit or a whole group."""

    kind: RowKind
    id: str
    name: str
    sort_key: str
    done: int
    total: int
    emoji: str | None = None

    @property
    def is_group(self) -> bool:
        return self.kind == "group"

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.done >= self.total

    @property
    def progress(self) -> GroupProgress:
        return GroupProgress(self.done, self.total)


@dataclass(frozen=True, slots=True)
class DayView:
    """Rows for one logical day, with tick totals (each tick counts)."""

    day: str
    rows: list[TodayRow] = field(default_factory=list)

    @property
    def done(self) -> int:
        return sum(r.done for r in self.rows)

    @property
    def total(self) -> int:
        return sum(r.total for r in self.rows)


@dataclass(frozen=True, slots=True)
class DayTotal:
    day: str
    done: int
    total: int


@dataclass(frozen=True, slots=True)
class HeatmapCell:
    day: str
    done: int
    total: int
    level: int  # 0 = nothing ticked yet, 1..4 = increasing share; see stats.shade_level
    ratio: float | None  # None when no habits were active that day


@dataclass(frozen=True, slots=True)
class ReviewView:
    today: str
    yesterday: DayView
    week: list[DayTotal]
    heatmap: list[list[HeatmapCell | None]]  # columns (weeks, Monday-first) of 7 cells
    showed_up_days: int
    window_days: int


@dataclass(frozen=True, slots=True)
class ArchiveToken:
    """Everything needed to undo one archive action."""

    kind: RowKind
    id: str
    name: str
    day: str
    member_ids: tuple[str, ...] = ()
