"""Use-cases. Everything the UI can do goes through `HabitService`."""

from __future__ import annotations

from collections import defaultdict
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, date, timedelta
from typing import Protocol

from habits.core import stats
from habits.core.clock import DEFAULT_DAY_START_HOUR, Clock, day_key, logical_day
from habits.core.ids import new_id
from habits.core.models import (
    MAX_GROUP_SIZE,
    MIN_GROUP_SIZE,
    ArchiveToken,
    Completion,
    CompletionState,
    DayView,
    Habit,
    HabitGroup,
    ReviewView,
    TodayRow,
)
from habits.core.parsing import parse_add, split_emoji
from habits.core.sortkeys import key_between


class Repository(Protocol):
    """Storage port. Implemented by `habits.db.repo.SqliteRepository`."""

    def transaction(self) -> AbstractContextManager[None]: ...

    def get_meta(self, key: str) -> str | None: ...
    def get_setting(self, key: str) -> str | None: ...

    def get_habit(self, habit_id: str) -> Habit | None: ...
    def get_group(self, group_id: str) -> HabitGroup | None: ...
    def insert_habit(self, habit: Habit) -> None: ...
    def update_habit(self, habit: Habit) -> None: ...
    def insert_group(self, group: HabitGroup) -> None: ...
    def update_group(self, group: HabitGroup) -> None: ...

    def list_habits(self) -> list[Habit]: ...
    def list_groups(self) -> list[HabitGroup]: ...
    def habits_active_on(self, day: str) -> list[Habit]: ...
    def groups_active_on(self, day: str) -> list[HabitGroup]: ...
    def group_members(self, group_id: str) -> list[Habit]: ...
    def max_top_level_sort_key(self) -> str | None: ...

    def completion_states(self, day: str) -> dict[str, CompletionState]: ...
    def done_between(self, start: str, end: str) -> set[tuple[str, str]]: ...
    def upsert_completion(self, completion: Completion) -> None: ...


class HabitService:
    def __init__(
        self,
        repo: Repository,
        clock: Clock,
        *,
        day_start_hour: int | None = None,
        device_id: str | None = None,
    ) -> None:
        self.repo = repo
        self.clock = clock
        if day_start_hour is None:
            stored = repo.get_setting("day_start_hour")
            day_start_hour = int(stored) if stored is not None else DEFAULT_DAY_START_HOUR
        if not 0 <= day_start_hour <= 23:
            raise ValueError(f"day_start_hour must be 0..23, got {day_start_hour}")
        self.day_start_hour = day_start_hour
        device_id = device_id or repo.get_meta("device_id")
        if not device_id:
            raise ValueError("no device_id; open the database with habits.db.connection")
        self.device_id = device_id

    # ---- time -------------------------------------------------------------

    def today_date(self) -> date:
        return logical_day(self.clock.now(), self.day_start_hour)

    def today(self) -> str:
        return day_key(self.today_date())

    def _stamp(self) -> str:
        return self.clock.now().astimezone(UTC).isoformat(timespec="microseconds")

    # ---- reading ------------------------------------------------------------

    def day_view(self, day: str) -> DayView:
        groups = self.repo.groups_active_on(day)
        habits = self.repo.habits_active_on(day)
        states = self.repo.completion_states(day)

        members: dict[str, list[Habit]] = defaultdict(list)
        rows: list[TodayRow] = []
        for h in habits:
            if h.group_id is None:
                done = 1 if states.get(h.id) == "done" else 0
                rows.append(TodayRow("habit", h.id, h.name, h.sort_key, done=done, total=1))
            else:
                members[h.group_id].append(h)
        for g in groups:
            ms = members.get(g.id, [])
            if not ms:
                continue
            done = sum(1 for m in ms if states.get(m.id) == "done")
            rows.append(
                TodayRow("group", g.id, g.name, g.sort_key, done=done, total=len(ms), emoji=g.emoji)
            )
        rows.sort(key=lambda r: (r.sort_key, r.id))
        return DayView(day=day, rows=rows)

    def today_view(self) -> DayView:
        return self.day_view(self.today())

    def review_view(self, weeks: int = 12, window_days: int = 14) -> ReviewView:
        today = self.today_date()
        start = min(stats.heatmap_start(today, weeks), today - timedelta(days=window_days - 1))
        days = [day_key(start + timedelta(days=i)) for i in range((today - start).days + 1)]

        habits = self.repo.list_habits()
        groups = {g.id: g for g in self.repo.list_groups()}
        done = self.repo.done_between(days[0], days[-1])
        totals = stats.day_totals(habits, groups, done, days)
        by_day = {t.day: t for t in totals}

        return ReviewView(
            today=day_key(today),
            yesterday=self.day_view(day_key(today - timedelta(days=1))),
            week=totals[-7:],
            heatmap=stats.heatmap_grid(by_day, today, weeks),
            showed_up_days=stats.showed_up_days(totals[-window_days:]),
            window_days=window_days,
        )

    # ---- completions ----------------------------------------------------------

    def _set_state(self, habit_id: str, state: CompletionState) -> None:
        self.repo.upsert_completion(
            Completion(
                habit_id=habit_id,
                day=self.today(),
                state=state,
                updated_at=self._stamp(),
                device_id=self.device_id,
            )
        )

    def _active_plain_habit(self, habit_id: str) -> Habit | None:
        h = self.repo.get_habit(habit_id)
        if h is None or h.group_id is not None or not h.active_on(self.today()):
            return None
        return h

    def toggle_habit(self, habit_id: str) -> bool | None:
        """Flip today's done state. Returns the new state, or None if not applicable."""
        if self._active_plain_habit(habit_id) is None:
            return None
        is_done = self.repo.completion_states(self.today()).get(habit_id) == "done"
        self._set_state(habit_id, "cleared" if is_done else "done")
        return not is_done

    def clear_habit(self, habit_id: str) -> bool:
        """Mark a plain habit not done today. Returns True if something changed."""
        if self._active_plain_habit(habit_id) is None:
            return False
        if self.repo.completion_states(self.today()).get(habit_id) != "done":
            return False
        self._set_state(habit_id, "cleared")
        return True

    def _active_members(self, group_id: str) -> list[Habit]:
        today = self.today()
        group = self.repo.get_group(group_id)
        if group is None or not group.active_on(today):
            return []
        return [m for m in self.repo.group_members(group_id) if m.active_on(today)]

    def tick_group(self, group_id: str) -> bool:
        """Tick the lowest open box. Returns True if a box was ticked."""
        states = self.repo.completion_states(self.today())
        for m in self._active_members(group_id):
            if states.get(m.id) != "done":
                self._set_state(m.id, "done")
                return True
        return False

    def clear_last(self, group_id: str) -> bool:
        """Clear the highest ticked box. Returns True if a box was cleared."""
        states = self.repo.completion_states(self.today())
        for m in reversed(self._active_members(group_id)):
            if states.get(m.id) == "done":
                self._set_state(m.id, "cleared")
                return True
        return False

    # ---- creating -------------------------------------------------------------

    def _next_sort_key(self) -> str:
        return key_between(self.repo.max_top_level_sort_key(), None)

    def add(self, text: str) -> str | None:
        """Add from the prompt text. Returns the new row id, or None for blank input."""
        parsed = parse_add(text)
        if parsed is None:
            return None
        if parsed.count is not None:
            return self.add_group(parsed.name, parsed.count, emoji=parsed.emoji).id
        return self.add_habit(parsed.name).id

    def add_habit(self, name: str) -> Habit:
        habit = Habit(
            id=new_id(),
            name=name.strip(),
            sort_key=self._next_sort_key(),
            created_day=self.today(),
            updated_at=self._stamp(),
        )
        self.repo.insert_habit(habit)
        return habit

    def add_group(self, name: str, count: int, *, emoji: str | None = None) -> HabitGroup:
        if not MIN_GROUP_SIZE <= count <= MAX_GROUP_SIZE:
            raise ValueError(f"group size must be {MIN_GROUP_SIZE}..{MAX_GROUP_SIZE}")
        today, stamp = self.today(), self._stamp()
        group = HabitGroup(
            id=new_id(),
            name=name.strip(),
            emoji=emoji,
            sort_key=self._next_sort_key(),
            created_day=today,
            updated_at=stamp,
        )
        with self.repo.transaction():
            self.repo.insert_group(group)
            for pos in range(1, count + 1):
                self.repo.insert_habit(self._member(group, pos, today, stamp))
        return group

    @staticmethod
    def _member(group: HabitGroup, pos: int, today: str, stamp: str) -> Habit:
        return Habit(
            id=new_id(),
            name=group.name,
            sort_key=group.sort_key,
            group_id=group.id,
            group_pos=pos,
            created_day=today,
            updated_at=stamp,
        )

    # ---- editing -------------------------------------------------------------

    def rename(self, item_id: str, text: str) -> bool:
        stamp = self._stamp()
        group = self.repo.get_group(item_id)
        if group is not None:
            emoji, name = split_emoji(" ".join(text.split()))
            if not name:
                return False
            with self.repo.transaction():
                self.repo.update_group(replace(group, name=name, emoji=emoji, updated_at=stamp))
                for m in self.repo.group_members(group.id):
                    self.repo.update_habit(replace(m, name=name, updated_at=stamp))
            return True
        habit = self.repo.get_habit(item_id)
        name = " ".join(text.split())
        if habit is None or habit.group_id is not None or not name:
            return False
        self.repo.update_habit(replace(habit, name=name, updated_at=stamp))
        return True

    def grow_group(self, group_id: str) -> bool:
        active = self._active_members(group_id)
        group = self.repo.get_group(group_id)
        if group is None or not active or len(active) >= MAX_GROUP_SIZE:
            return False
        top = max((m.group_pos or 0) for m in self.repo.group_members(group_id))
        self.repo.insert_habit(self._member(group, top + 1, self.today(), self._stamp()))
        return True

    def shrink_group(self, group_id: str) -> bool:
        active = self._active_members(group_id)
        if len(active) <= MIN_GROUP_SIZE:
            return False
        last = active[-1]
        self.repo.update_habit(replace(last, archived_day=self.today(), updated_at=self._stamp()))
        return True

    def move(self, item_id: str, delta: int) -> bool:
        """Move a row up (delta<0) or down (delta>0) in today's list."""
        rows = self.today_view().rows
        idx = next((i for i, r in enumerate(rows) if r.id == item_id), None)
        if idx is None or delta == 0:
            return False
        target = idx + delta
        if not 0 <= target < len(rows):
            return False
        others = [r for r in rows if r.id != item_id]
        before = others[target - 1].sort_key if target > 0 else None
        after = others[target].sort_key if target < len(others) else None
        if before is not None and after is not None and before >= after:
            self._renumber(others)
            return self.move(item_id, delta)
        self._set_sort_key(rows[idx], key_between(before, after))
        return True

    def _renumber(self, rows: list[TodayRow]) -> None:
        """Give rows fresh, strictly increasing keys (only needed after key collisions)."""
        key: str | None = None
        with self.repo.transaction():
            for r in rows:
                key = key_between(key, None)
                self._set_sort_key(r, key)

    def _set_sort_key(self, row: TodayRow, key: str) -> None:
        stamp = self._stamp()
        if row.is_group:
            group = self.repo.get_group(row.id)
            if group is not None:
                self.repo.update_group(replace(group, sort_key=key, updated_at=stamp))
        else:
            habit = self.repo.get_habit(row.id)
            if habit is not None:
                self.repo.update_habit(replace(habit, sort_key=key, updated_at=stamp))

    # ---- archive / restore -----------------------------------------------------

    def archive(self, item_id: str) -> ArchiveToken | None:
        today, stamp = self.today(), self._stamp()
        group = self.repo.get_group(item_id)
        if group is not None:
            if not group.active_on(today):
                return None
            members = [m for m in self.repo.group_members(group.id) if m.archived_day is None]
            with self.repo.transaction():
                self.repo.update_group(replace(group, archived_day=today, updated_at=stamp))
                for m in members:
                    self.repo.update_habit(replace(m, archived_day=today, updated_at=stamp))
            return ArchiveToken("group", group.id, group.name, today, tuple(m.id for m in members))
        habit = self.repo.get_habit(item_id)
        if habit is None or habit.group_id is not None or not habit.active_on(today):
            return None
        self.repo.update_habit(replace(habit, archived_day=today, updated_at=stamp))
        return ArchiveToken("habit", habit.id, habit.name, today)

    def restore(self, token: ArchiveToken) -> bool:
        """Undo an archive made today. Past days are read-only, so older tokens are refused."""
        if token.day != self.today():
            return False
        stamp = self._stamp()
        if token.kind == "group":
            group = self.repo.get_group(token.id)
            if group is None or group.archived_day != token.day:
                return False
            with self.repo.transaction():
                self.repo.update_group(replace(group, archived_day=None, updated_at=stamp))
                for mid in token.member_ids:
                    m = self.repo.get_habit(mid)
                    if m is not None and m.archived_day == token.day:
                        self.repo.update_habit(replace(m, archived_day=None, updated_at=stamp))
            return True
        habit = self.repo.get_habit(token.id)
        if habit is None or habit.archived_day != token.day:
            return False
        self.repo.update_habit(replace(habit, archived_day=None, updated_at=stamp))
        return True
