"""SQL lives here and nowhere else. Returns core models."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

from habits.core.models import Completion, CompletionState, Habit, HabitGroup

_HABIT_COLS = "id, name, sort_key, group_id, group_pos, created_day, archived_day, updated_at"
_GROUP_COLS = "id, name, emoji, sort_key, created_day, archived_day, updated_at"
_ACTIVE = "created_day <= :day AND (archived_day IS NULL OR archived_day > :day)"


def _habit(row: sqlite3.Row) -> Habit:
    return Habit(
        id=row["id"],
        name=row["name"],
        sort_key=row["sort_key"],
        group_id=row["group_id"],
        group_pos=row["group_pos"],
        created_day=row["created_day"],
        archived_day=row["archived_day"],
        updated_at=row["updated_at"],
    )


def _group(row: sqlite3.Row) -> HabitGroup:
    return HabitGroup(
        id=row["id"],
        name=row["name"],
        emoji=row["emoji"],
        sort_key=row["sort_key"],
        created_day=row["created_day"],
        archived_day=row["archived_day"],
        updated_at=row["updated_at"],
    )


class SqliteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._depth = 0

    # ---- transactions -----------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """A transaction; nested calls join the outer one."""
        if self._depth:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")
        finally:
            self._depth = 0

    def _one(self, sql: str, params: Any = ()) -> sqlite3.Row | None:
        return cast(sqlite3.Row | None, self.conn.execute(sql, params).fetchone())

    def _all(self, sql: str, params: Any = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    # ---- meta / settings ------------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        row = self._one("SELECT value FROM meta WHERE key = ?", (key,))
        return None if row is None else str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def get_setting(self, key: str) -> str | None:
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ---- habits ---------------------------------------------------------------

    def get_habit(self, habit_id: str) -> Habit | None:
        row = self._one(f"SELECT {_HABIT_COLS} FROM habits WHERE id = ?", (habit_id,))
        return None if row is None else _habit(row)

    def insert_habit(self, habit: Habit) -> None:
        self.conn.execute(
            f"INSERT INTO habits ({_HABIT_COLS}) VALUES "
            "(:id, :name, :sort_key, :group_id, :group_pos, :created_day, :archived_day, "
            ":updated_at)",
            _habit_params(habit),
        )

    def update_habit(self, habit: Habit) -> None:
        self.conn.execute(
            "UPDATE habits SET name = :name, sort_key = :sort_key, group_id = :group_id, "
            "group_pos = :group_pos, created_day = :created_day, archived_day = :archived_day, "
            "updated_at = :updated_at WHERE id = :id",
            _habit_params(habit),
        )

    def list_habits(self) -> list[Habit]:
        return [_habit(r) for r in self._all(f"SELECT {_HABIT_COLS} FROM habits")]

    def habits_active_on(self, day: str) -> list[Habit]:
        rows = self._all(
            f"SELECT {_HABIT_COLS} FROM habits WHERE {_ACTIVE} "
            "ORDER BY group_id, group_pos, sort_key, id",
            {"day": day},
        )
        return [_habit(r) for r in rows]

    def group_members(self, group_id: str) -> list[Habit]:
        rows = self._all(
            f"SELECT {_HABIT_COLS} FROM habits WHERE group_id = ? ORDER BY group_pos",
            (group_id,),
        )
        return [_habit(r) for r in rows]

    def max_top_level_sort_key(self) -> str | None:
        row = self._one(
            "SELECT MAX(k) AS k FROM ("
            "  SELECT sort_key AS k FROM habits WHERE group_id IS NULL"
            "  UNION ALL SELECT sort_key FROM habit_groups)"
        )
        return None if row is None or row["k"] is None else str(row["k"])

    # ---- groups ---------------------------------------------------------------

    def get_group(self, group_id: str) -> HabitGroup | None:
        row = self._one(f"SELECT {_GROUP_COLS} FROM habit_groups WHERE id = ?", (group_id,))
        return None if row is None else _group(row)

    def insert_group(self, group: HabitGroup) -> None:
        self.conn.execute(
            f"INSERT INTO habit_groups ({_GROUP_COLS}) VALUES "
            "(:id, :name, :emoji, :sort_key, :created_day, :archived_day, :updated_at)",
            _group_params(group),
        )

    def update_group(self, group: HabitGroup) -> None:
        self.conn.execute(
            "UPDATE habit_groups SET name = :name, emoji = :emoji, sort_key = :sort_key, "
            "created_day = :created_day, archived_day = :archived_day, updated_at = :updated_at "
            "WHERE id = :id",
            _group_params(group),
        )

    def list_groups(self) -> list[HabitGroup]:
        return [_group(r) for r in self._all(f"SELECT {_GROUP_COLS} FROM habit_groups")]

    def groups_active_on(self, day: str) -> list[HabitGroup]:
        rows = self._all(
            f"SELECT {_GROUP_COLS} FROM habit_groups WHERE {_ACTIVE} ORDER BY sort_key, id",
            {"day": day},
        )
        return [_group(r) for r in rows]

    # ---- completions ------------------------------------------------------------

    def completion_states(self, day: str) -> dict[str, CompletionState]:
        rows = self._all("SELECT habit_id, state FROM completions WHERE day = ?", (day,))
        return {r["habit_id"]: r["state"] for r in rows}

    def get_completion(self, habit_id: str, day: str) -> Completion | None:
        row = self._one(
            "SELECT habit_id, day, state, updated_at, device_id FROM completions "
            "WHERE habit_id = ? AND day = ?",
            (habit_id, day),
        )
        if row is None:
            return None
        return Completion(
            habit_id=row["habit_id"],
            day=row["day"],
            state=row["state"],
            updated_at=row["updated_at"],
            device_id=row["device_id"],
        )

    def done_between(self, start: str, end: str) -> set[tuple[str, str]]:
        rows = self._all(
            "SELECT habit_id, day FROM completions WHERE day >= ? AND day <= ? AND state = 'done'",
            (start, end),
        )
        return {(r["habit_id"], r["day"]) for r in rows}

    def upsert_completion(self, completion: Completion) -> None:
        self.conn.execute(
            "INSERT INTO completions (habit_id, day, state, updated_at, device_id) "
            "VALUES (:habit_id, :day, :state, :updated_at, :device_id) "
            "ON CONFLICT(habit_id, day) DO UPDATE SET state = excluded.state, "
            "updated_at = excluded.updated_at, device_id = excluded.device_id",
            {
                "habit_id": completion.habit_id,
                "day": completion.day,
                "state": completion.state,
                "updated_at": completion.updated_at,
                "device_id": completion.device_id,
            },
        )


def _habit_params(h: Habit) -> dict[str, Any]:
    return {
        "id": h.id,
        "name": h.name,
        "sort_key": h.sort_key,
        "group_id": h.group_id,
        "group_pos": h.group_pos,
        "created_day": h.created_day,
        "archived_day": h.archived_day,
        "updated_at": h.updated_at,
    }


def _group_params(g: HabitGroup) -> dict[str, Any]:
    return {
        "id": g.id,
        "name": g.name,
        "emoji": g.emoji,
        "sort_key": g.sort_key,
        "created_day": g.created_day,
        "archived_day": g.archived_day,
        "updated_at": g.updated_at,
    }
