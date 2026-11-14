"""Visual snapshots. Update with: uv run pytest tests/ui/test_snapshots.py --snapshot-update"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from habits.core.clock import ManualClock
from habits.core.service import HabitService
from habits.ui.app import HabitsApp

SIZE = (80, 34)
SnapCompare = Callable[..., bool]


def seeded(service: HabitService, clock: ManualClock) -> HabitsApp:
    """Two weeks of deterministic history, ending on Saturday 14 Nov 2026."""
    clock.advance(timedelta(days=-13))
    read = service.add("Read")
    water = service.add("💧 Water x8")
    run = service.add("Run")
    assert read and water and run
    for i in range(14):
        if i % 2 == 0:
            service.toggle_habit(read)
        if i % 3 == 0:
            service.toggle_habit(run)
        for _ in range(i % 9):
            service.tick_group(water)
        if i < 13:
            clock.advance(timedelta(days=1))
    return HabitsApp(service)


def test_today_snapshot(snap_compare: SnapCompare, service: HabitService, clock: Any) -> None:
    assert snap_compare(seeded(service, clock), terminal_size=SIZE, press=["j"])


def test_today_empty_snapshot(snap_compare: SnapCompare, service: HabitService) -> None:
    assert snap_compare(HabitsApp(service), terminal_size=SIZE)


def test_review_snapshot(snap_compare: SnapCompare, service: HabitService, clock: Any) -> None:
    assert snap_compare(seeded(service, clock), terminal_size=SIZE, press=["tab"])
