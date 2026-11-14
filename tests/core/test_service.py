from __future__ import annotations

from datetime import timedelta

import pytest

from habits.core.clock import ManualClock
from habits.core.models import DayView, TodayRow
from habits.core.service import HabitService
from habits.db.repo import SqliteRepository
from tests.conftest import at


def row(view: DayView, name: str) -> TodayRow:
    return next(r for r in view.rows if r.name == name)


def names(service: HabitService) -> list[str]:
    return [r.name for r in service.today_view().rows]


def next_day(clock: ManualClock) -> None:
    clock.advance(timedelta(days=1))


# ---- basics ----------------------------------------------------------------------


def test_requires_device_id(repo: SqliteRepository, clock: ManualClock) -> None:
    repo.conn.execute("DELETE FROM meta")
    with pytest.raises(ValueError):
        HabitService(repo, clock)


def test_day_start_hour_from_settings_and_override(
    repo: SqliteRepository, clock: ManualClock
) -> None:
    clock.set(at(2026, 11, 15, 4, 30))
    assert HabitService(repo, clock).today() == "2026-11-14"
    assert HabitService(repo, clock, day_start_hour=4).today() == "2026-11-15"
    repo.set_setting("day_start_hour", "4")
    assert HabitService(repo, clock).today() == "2026-11-15"
    with pytest.raises(ValueError):
        HabitService(repo, clock, day_start_hour=24)


def test_add_and_toggle(service: HabitService) -> None:
    hid = service.add("Read")
    assert hid is not None
    view = service.today_view()
    assert [(r.name, r.done, r.total) for r in view.rows] == [("Read", 0, 1)]
    assert service.toggle_habit(hid) is True
    assert service.today_view().done == 1
    assert service.toggle_habit(hid) is False
    assert service.today_view().done == 0
    assert service.add("   ") is None


def test_toggle_writes_tombstone_with_metadata(
    service: HabitService, repo: SqliteRepository
) -> None:
    hid = service.add("Read")
    assert hid
    service.toggle_habit(hid)
    service.toggle_habit(hid)
    c = repo.get_completion(hid, "2026-11-14")
    assert c is not None
    assert c.state == "cleared"
    assert c.device_id == service.device_id
    assert c.updated_at.endswith("+00:00")


def test_clear_habit(service: HabitService) -> None:
    hid = service.add("Read")
    assert hid
    assert service.clear_habit(hid) is False
    service.toggle_habit(hid)
    assert service.clear_habit(hid) is True
    assert service.today_view().done == 0


def test_writes_go_to_logical_day(service: HabitService, clock: ManualClock) -> None:
    hid = service.add("Read")
    assert hid
    clock.set(at(2026, 11, 15, 2, 0))  # 2am Sunday is still Saturday
    service.toggle_habit(hid)
    assert service.day_view("2026-11-14").done == 1
    clock.set(at(2026, 11, 15, 5, 0))
    assert service.today() == "2026-11-15"
    assert service.today_view().done == 0
    # yesterday stays as it was
    assert service.day_view("2026-11-14").done == 1


def test_habit_not_active_before_creation(service: HabitService, clock: ManualClock) -> None:
    service.add("Read")
    assert service.day_view("2026-11-13").rows == []


def test_interleaved_order(service: HabitService) -> None:
    service.add("A")
    service.add("Water x3")
    service.add("B")
    assert names(service) == ["A", "Water", "B"]


# ---- groups ------------------------------------------------------------------------


def test_add_group_creates_members(service: HabitService, repo: SqliteRepository) -> None:
    gid = service.add("💧 Water x8")
    assert gid
    g = repo.get_group(gid)
    assert g is not None and g.emoji == "💧" and g.name == "Water"
    assert [m.group_pos for m in repo.group_members(gid)] == list(range(1, 9))
    r = service.today_view().rows[0]
    assert (r.kind, r.done, r.total, r.emoji) == ("group", 0, 8, "💧")


def test_add_group_is_atomic(service: HabitService, repo: SqliteRepository) -> None:
    original = repo.insert_habit
    calls = 0

    def flaky(h):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("disk on fire")
        original(h)

    repo.insert_habit = flaky  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        service.add("Water x8")
    assert repo.list_groups() == []
    assert repo.list_habits() == []


def test_tick_fills_lowest_and_stops_when_full(
    service: HabitService, repo: SqliteRepository
) -> None:
    gid = service.add("Water x3")
    assert gid
    members = repo.group_members(gid)
    assert service.tick_group(gid)
    assert repo.completion_states(service.today()) == {members[0].id: "done"}
    assert service.tick_group(gid)
    assert service.tick_group(gid)
    assert service.tick_group(gid) is False  # full: no wrap, no error
    assert row(service.today_view(), "Water").done == 3


def test_clear_last_clears_highest(service: HabitService, repo: SqliteRepository) -> None:
    gid = service.add("Water x4")
    assert gid
    members = repo.group_members(gid)
    assert service.clear_last(gid) is False
    for _ in range(3):
        service.tick_group(gid)
    assert service.clear_last(gid)
    states = repo.completion_states(service.today())
    assert states[members[2].id] == "cleared"
    assert states[members[1].id] == "done"
    assert row(service.today_view(), "Water").done == 2
    # tick refills the cleared slot first
    service.tick_group(gid)
    assert repo.completion_states(service.today())[members[2].id] == "done"


def test_group_rows_not_toggleable_as_habit(service: HabitService, repo: SqliteRepository) -> None:
    gid = service.add("Water x2")
    assert gid
    member = repo.group_members(gid)[0]
    assert service.toggle_habit(member.id) is None
    assert service.toggle_habit(gid) is None


def test_grow_and_shrink_limits(service: HabitService) -> None:
    gid = service.add("Water x2")
    assert gid
    assert service.shrink_group(gid) is False  # min 2
    for _ in range(48):
        assert service.grow_group(gid)
    assert row(service.today_view(), "Water").total == 50
    assert service.grow_group(gid) is False  # max 50


def test_resize_keeps_past_denominators(
    service: HabitService, repo: SqliteRepository, clock: ManualClock
) -> None:
    gid = service.add("Water x8")
    assert gid
    for _ in range(3):
        service.tick_group(gid)

    next_day(clock)  # Sunday
    assert service.grow_group(gid)
    assert service.grow_group(gid)
    assert row(service.today_view(), "Water").total == 10
    assert row(service.day_view("2026-11-14"), "Water").total == 8
    assert row(service.day_view("2026-11-14"), "Water").done == 3

    next_day(clock)  # Monday
    for _ in range(5):
        assert service.shrink_group(gid)
    assert row(service.today_view(), "Water").total == 5
    assert row(service.day_view("2026-11-15"), "Water").total == 10
    assert row(service.day_view("2026-11-14"), "Water").total == 8
    # new members keep increasing positions
    assert [m.group_pos for m in repo.group_members(gid)] == list(range(1, 11))


def test_shrink_same_day_then_grow(service: HabitService, repo: SqliteRepository) -> None:
    gid = service.add("Water x3")
    assert gid
    service.shrink_group(gid)
    service.grow_group(gid)
    assert row(service.today_view(), "Water").total == 3
    assert [m.group_pos for m in repo.group_members(gid)] == [1, 2, 3, 4]


def test_shrink_drops_a_done_top_box(service: HabitService) -> None:
    gid = service.add("Water x3")
    assert gid
    for _ in range(3):
        service.tick_group(gid)
    service.shrink_group(gid)
    r = row(service.today_view(), "Water")
    assert (r.done, r.total) == (2, 2)


def test_rename_habit_and_group(service: HabitService, repo: SqliteRepository) -> None:
    hid = service.add("Read")
    gid = service.add("💧 Water x2")
    assert hid and gid
    assert service.rename(hid, "  Read  daily ")
    assert service.rename(gid, "🥤 Hydrate")
    assert service.rename(hid, "   ") is False
    view = service.today_view()
    assert [r.name for r in view.rows] == ["Read daily", "Hydrate"]
    assert view.rows[1].emoji == "🥤"
    assert {m.name for m in repo.group_members(gid)} == {"Hydrate"}
    service.rename(gid, "Water")
    assert service.today_view().rows[1].emoji is None


# ---- archive / restore -----------------------------------------------------------


def test_archive_and_restore_habit(service: HabitService, clock: ManualClock) -> None:
    hid = service.add("Read")
    assert hid
    service.toggle_habit(hid)
    next_day(clock)
    token = service.archive(hid)
    assert token is not None and token.kind == "habit"
    assert service.today_view().rows == []
    # history kept: Saturday still shows it done
    assert service.day_view("2026-11-14").done == 1
    assert service.archive(hid) is None
    assert service.restore(token)
    assert names(service) == ["Read"]


def test_archive_restore_group_as_unit(
    service: HabitService, repo: SqliteRepository, clock: ManualClock
) -> None:
    gid = service.add("Water x4")
    assert gid
    next_day(clock)
    service.shrink_group(gid)  # pos 4 archived Sunday on its own
    next_day(clock)
    token = service.archive(gid)
    assert token is not None and token.kind == "group"
    assert len(token.member_ids) == 3
    assert service.today_view().rows == []
    assert all(m.archived_day for m in repo.group_members(gid))
    assert service.restore(token)
    r = row(service.today_view(), "Water")
    assert r.total == 3  # the separately shrunk member stays archived
    assert row(service.day_view("2026-11-14"), "Water").total == 4


def test_restore_refused_after_rollover(service: HabitService, clock: ManualClock) -> None:
    hid = service.add("Read")
    assert hid
    token = service.archive(hid)
    assert token
    next_day(clock)
    assert service.restore(token) is False


def test_archived_keeps_position_on_restore(service: HabitService) -> None:
    service.add("A")
    bid = service.add("B")
    service.add("C")
    assert bid
    token = service.archive(bid)
    assert token
    service.add("D")
    service.restore(token)
    assert names(service) == ["A", "B", "C", "D"]


# ---- reorder ---------------------------------------------------------------------------


def test_move_rows(service: HabitService) -> None:
    a = service.add("A")
    service.add("Water x3")
    c = service.add("C")
    assert a and c
    assert service.move(a, +1)
    assert names(service) == ["Water", "A", "C"]
    assert service.move(a, +1)
    assert names(service) == ["Water", "C", "A"]
    assert service.move(a, +1) is False
    assert service.move(c, -1)
    assert names(service) == ["C", "Water", "A"]
    assert service.move(c, -1) is False


def test_move_group_as_single_row(service: HabitService) -> None:
    service.add("A")
    gid = service.add("Water x3")
    assert gid
    assert service.move(gid, -1)
    assert names(service) == ["Water", "A"]


def test_move_recovers_from_key_collisions(service: HabitService, repo: SqliteRepository) -> None:
    ids = [service.add(n) for n in "ABC"]
    repo.conn.execute("UPDATE habits SET sort_key = 'V'")
    expected = [r.name for r in service.today_view().rows]  # tie-broken by id
    moved = service.today_view().rows[0]
    assert service.move(moved.id, +1)
    assert names(service) == [expected[1], expected[0], expected[2]]
    assert len({h.sort_key for h in repo.list_habits()}) == 3
    assert all(ids)


def test_many_moves_stay_consistent(service: HabitService) -> None:
    ids = [service.add(str(i)) for i in range(6)]
    assert all(ids)
    for _ in range(30):
        service.move(ids[0] or "", +1)
        service.move(ids[0] or "", +1)
        service.move(ids[0] or "", -1)
    assert sorted(names(service)) == [str(i) for i in range(6)]
