from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from textual.widgets import Input, Static

from habits.core.clock import ManualClock
from habits.core.service import HabitService
from habits.db.connection import connect
from habits.db.repo import SqliteRepository
from habits.ui.app import HabitsApp
from habits.ui.screens.review import ReviewScreen
from habits.ui.screens.today import TodayScreen
from habits.ui.widgets.habit_row import Row
from tests.conftest import at


def today(app: HabitsApp) -> TodayScreen:
    screen = app.screen
    assert isinstance(screen, TodayScreen)
    return screen


def lines(app: HabitsApp) -> list[str]:
    return [str(w.render()) for w in today(app).query(Row)]


def cursor_name(app: HabitsApp) -> str | None:
    row = today(app).current
    return row.name if row else None


def progress(app: HabitsApp) -> str:
    return str(today(app).query_one("#progress", Static).render())


def seed(service: HabitService) -> None:
    service.add("Read")
    service.add("💧 Water x3")
    service.add("Stretch")


async def test_empty_state(service: HabitService) -> None:
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert today(app).query_one("#empty").display is True
        assert lines(app) == []
        await pilot.press("space", "d", "plus", "j")  # nothing to act on: no errors


async def test_navigation(service: HabitService) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert lines(app) == ["[ ] Read", "💧 Water □□□ 0/3", "[ ] Stretch"]
        assert cursor_name(app) == "Read"
        await pilot.press("j")
        assert cursor_name(app) == "Water"
        await pilot.press("down", "down")  # clamps at the end
        assert cursor_name(app) == "Stretch"
        await pilot.press("k")
        assert cursor_name(app) == "Water"
        await pilot.press("g")
        assert cursor_name(app) == "Read"
        await pilot.press("G")
        assert cursor_name(app) == "Stretch"
        await pilot.press("up", "up", "up")
        assert cursor_name(app) == "Read"


async def test_toggle_advances_but_untoggle_stays(service: HabitService) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert progress(app) == "Fresh day, ready when you are"
        await pilot.press("space")
        assert lines(app)[0] == "[x] Read"
        assert cursor_name(app) == "Water"
        assert progress(app) == "1 of 5 today"
        await pilot.press("k", "enter")  # un-toggle: stay put
        assert lines(app)[0] == "[ ] Read"
        assert cursor_name(app) == "Read"


async def test_group_tick_and_clear(service: HabitService) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j", "space", "space")
        assert lines(app)[1] == "💧 Water ▪▪□ 2/3"
        assert cursor_name(app) == "Water"  # partial: no advance
        await pilot.press("backspace")
        assert lines(app)[1] == "💧 Water ▪□□ 1/3"
        await pilot.press("space", "space")
        assert lines(app)[1] == "💧 Water ▪▪▪ 3/3"
        assert cursor_name(app) == "Stretch"  # fully done: advance
        assert progress(app) == "3 of 5 today"
        await pilot.press("k", "space")  # full group: nothing happens
        assert lines(app)[1] == "💧 Water ▪▪▪ 3/3"


async def test_backspace_clears_plain_habit(service: HabitService) -> None:
    service.add("Read")
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space", "backspace")
        assert lines(app) == ["[ ] Read"]


async def test_add_habit_and_group(service: HabitService) -> None:
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        assert isinstance(app.focused, Input)
        await pilot.press(*"Read", "enter")
        await pilot.pause()
        assert lines(app) == ["[ ] Read"]
        await pilot.press("a")
        await pilot.press(*"Water x4", "enter")
        await pilot.pause()
        assert lines(app) == ["[ ] Read", "Water □□□□ 0/4"]
        assert cursor_name(app) == "Water"  # cursor jumps to the new row
        await pilot.press("a", *"never mind", "escape")
        await pilot.pause()
        assert len(lines(app)) == 2


async def test_rename(service: HabitService) -> None:
    service.add("💧 Water x2")
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        field = app.screen.query_one(Input)
        assert field.value == "💧 Water"
        field.value = "🥤 Juice"
        await pilot.press("enter")
        await pilot.pause()
        assert lines(app) == ["🥤 Juice □□ 0/2"]


async def test_archive_and_undo(service: HabitService) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("j", "d")
        await pilot.pause()
        assert lines(app) == ["[ ] Read", "[ ] Stretch"]
        assert cursor_name(app) == "Stretch"
        await pilot.press("g", "d")
        await pilot.pause()
        assert lines(app) == ["[ ] Stretch"]
        await pilot.press("u")
        await pilot.pause()
        assert lines(app) == ["[ ] Read", "[ ] Stretch"]
        assert cursor_name(app) == "Read"
        await pilot.press("u")
        await pilot.pause()
        assert lines(app) == ["[ ] Read", "💧 Water □□□ 0/3", "[ ] Stretch"]
        assert cursor_name(app) == "Water"
        await pilot.press("u")  # nothing left: gentle no-op
        await pilot.pause()
        assert len(lines(app)) == 3


async def test_resize_group(service: HabitService) -> None:
    service.add("Water x2")
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("plus", "plus")
        assert lines(app) == ["Water □□□□ 0/4"]
        await pilot.press("minus", "minus", "minus")  # stops at 2
        assert lines(app) == ["Water □□ 0/2"]


async def test_reorder(service: HabitService) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("J")
        assert [line.split()[-1] for line in lines(app)] == ["0/3", "Read", "Stretch"]
        assert cursor_name(app) == "Read"
        await pilot.press("J", "J")
        assert cursor_name(app) == "Read"
        assert lines(app)[-1] == "[ ] Read"
        await pilot.press("g", "K")  # already first
        await pilot.press("G", "K")
        assert lines(app) == ["💧 Water □□□ 0/3", "[ ] Read", "[ ] Stretch"]


async def test_footer_hides_group_keys_on_plain_rows(service: HabitService) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = today(app)
        assert screen.check_action("grow", ()) is False
        await pilot.press("j")
        assert screen.check_action("grow", ()) is True


async def test_tab_switches_screens(service: HabitService) -> None:
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert isinstance(app.screen, ReviewScreen)
        await pilot.press("tab")
        await pilot.pause()
        assert isinstance(app.screen, TodayScreen)


async def test_help_opens_and_closes(service: HabitService) -> None:
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert type(app.screen).__name__ == "HelpScreen"
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, TodayScreen)


async def test_quit(service: HabitService) -> None:
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
    assert app.return_code == 0


async def test_state_persists_across_restarts(tmp_path: Path, clock: ManualClock) -> None:
    path = tmp_path / "habits.db"
    conn = connect(path)
    service = HabitService(SqliteRepository(conn), clock)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.press("a", *"Read", "enter")
        await pilot.press("a", *"Water x3", "enter")
        await pilot.pause()
        await pilot.press("g", "space", "space")
        await pilot.pause()
    conn.close()

    conn = connect(path)
    app = HabitsApp(HabitService(SqliteRepository(conn), clock))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert lines(app) == ["[x] Read", "Water ▪□□ 1/3"]
    conn.close()


async def test_rollover_swaps_to_new_day(service: HabitService, clock: ManualClock) -> None:
    seed(service)
    clock.set(at(2026, 11, 15, 4, 59))  # 4:59am Sunday: still Saturday
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("space", "space", "space")  # Read, then 2 Water boxes
        assert lines(app) == ["[x] Read", "💧 Water ▪▪□ 2/3", "[ ] Stretch"]
        await pilot.press("G", "d")  # archive Stretch; leaves an undo entry
        await pilot.pause()
        assert cursor_name(app) == "Water"  # cursor stays at the same index, clamped
        assert app.undo_stack
        assert await app.check_rollover() is False

        clock.advance(timedelta(minutes=1))  # 5:00am: Sunday
        assert await app.check_rollover() is True
        await pilot.pause()
        assert app.current_day == "2026-11-15"
        assert lines(app) == ["[ ] Read", "💧 Water □□□ 0/3"]
        assert progress(app) == "Fresh day, ready when you are"
        assert cursor_name(app) == "Water"  # cursor kept by row identity
        assert app.undo_stack == []  # Saturday's archive can't be undone on Sunday
        # Saturday is untouched and read-only.
        assert service.day_view("2026-11-14").done == 3


async def test_rollover_while_on_review(service: HabitService, clock: ManualClock) -> None:
    seed(service)
    app = HabitsApp(service)
    async with app.run_test() as pilot:
        await pilot.press("space")
        await pilot.press("tab")
        await pilot.pause()
        clock.advance(timedelta(days=1))
        assert await app.check_rollover() is True
        await pilot.pause()
        review = app.screen
        assert isinstance(review, ReviewScreen)
        summary = str(review.query_one("#yesterday-summary", Static).render())
        assert summary == "You did 1 of 5 yesterday"
        await pilot.press("tab")
        await pilot.pause()
        assert lines(app)[0] == "[ ] Read"
