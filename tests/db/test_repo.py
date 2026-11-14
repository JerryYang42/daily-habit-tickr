from __future__ import annotations

import sqlite3
from dataclasses import replace

import pytest

from habits.core.models import Completion, Habit, HabitGroup
from habits.db.repo import SqliteRepository

DAY = "2026-11-14"


def habit(id: str = "h1", **kw: object) -> Habit:
    base = Habit(id=id, name="Read", sort_key="V", created_day=DAY, updated_at="t0")
    return replace(base, **kw)  # type: ignore[arg-type]


def group(id: str = "g1", **kw: object) -> HabitGroup:
    base = HabitGroup(
        id=id, name="Water", emoji="💧", sort_key="k", created_day=DAY, updated_at="t0"
    )
    return replace(base, **kw)  # type: ignore[arg-type]


def test_habit_round_trip(repo: SqliteRepository) -> None:
    h = habit()
    repo.insert_habit(h)
    assert repo.get_habit("h1") == h
    h2 = replace(h, name="Read more", archived_day="2026-11-20", updated_at="t1")
    repo.update_habit(h2)
    assert repo.get_habit("h1") == h2
    assert repo.list_habits() == [h2]
    assert repo.get_habit("nope") is None


def test_group_round_trip(repo: SqliteRepository) -> None:
    g = group()
    repo.insert_group(g)
    members = [habit(f"m{i}", group_id="g1", group_pos=i, sort_key="k") for i in (2, 1, 3)]
    for m in members:
        repo.insert_habit(m)
    assert repo.get_group("g1") == g
    assert [m.group_pos for m in repo.group_members("g1")] == [1, 2, 3]
    repo.update_group(replace(g, emoji=None, name="H2O"))
    got = repo.get_group("g1")
    assert got is not None and got.emoji is None and got.name == "H2O"
    assert repo.list_groups() == [got]


def test_foreign_keys_enforced(repo: SqliteRepository) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_habit(habit(group_id="missing", group_pos=1))


def test_active_on_filters(repo: SqliteRepository) -> None:
    repo.insert_habit(habit("past", created_day="2026-11-01", archived_day="2026-11-10"))
    repo.insert_habit(habit("now", created_day="2026-11-01"))
    repo.insert_habit(habit("future", created_day="2026-11-20"))
    repo.insert_habit(habit("ends_today", created_day="2026-11-01", archived_day=DAY))
    assert {h.id for h in repo.habits_active_on(DAY)} == {"now"}
    assert {h.id for h in repo.habits_active_on("2026-11-09")} == {"past", "now", "ends_today"}
    repo.insert_group(group(created_day="2026-11-12", archived_day="2026-11-13"))
    assert [g.id for g in repo.groups_active_on("2026-11-12")] == ["g1"]
    assert repo.groups_active_on(DAY) == []


def test_completion_upsert_and_tombstone(repo: SqliteRepository) -> None:
    repo.insert_habit(habit())
    repo.upsert_completion(Completion("h1", DAY, "done", "t1", "dev"))
    assert repo.completion_states(DAY) == {"h1": "done"}
    repo.upsert_completion(Completion("h1", DAY, "cleared", "t2", "dev2"))
    assert repo.get_completion("h1", DAY) == Completion("h1", DAY, "cleared", "t2", "dev2")
    # tombstone row is kept, never deleted
    assert repo.conn.execute("SELECT COUNT(*) FROM completions").fetchone()[0] == 1
    assert repo.done_between("2026-11-01", "2026-11-30") == set()


def test_done_between(repo: SqliteRepository) -> None:
    repo.insert_habit(habit())
    for day in ("2026-11-10", "2026-11-12", "2026-11-14"):
        repo.upsert_completion(Completion("h1", day, "done", "t", "dev"))
    assert repo.done_between("2026-11-11", "2026-11-14") == {
        ("h1", "2026-11-12"),
        ("h1", "2026-11-14"),
    }


def test_max_top_level_sort_key(repo: SqliteRepository) -> None:
    assert repo.max_top_level_sort_key() is None
    repo.insert_habit(habit(sort_key="V"))
    repo.insert_group(group(sort_key="k"))
    repo.insert_habit(habit("m1", group_id="g1", group_pos=1, sort_key="z"))  # members ignored
    assert repo.max_top_level_sort_key() == "k"


def test_transaction_rolls_back(repo: SqliteRepository) -> None:
    with pytest.raises(RuntimeError), repo.transaction():
        repo.insert_habit(habit("a"))
        with repo.transaction():
            repo.insert_habit(habit("b"))
        raise RuntimeError("boom")
    assert repo.list_habits() == []


def test_meta_and_settings(repo: SqliteRepository) -> None:
    assert repo.get_meta("device_id")
    assert repo.get_setting("day_start_hour") == "5"
    repo.set_setting("day_start_hour", "4")
    repo.set_meta("k", "v")
    assert repo.get_setting("day_start_hour") == "4"
    assert repo.get_meta("k") == "v"
