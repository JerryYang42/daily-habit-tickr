"""The Textual app: screens, undo stack, and the 5am rollover."""

from __future__ import annotations

from textual.app import App
from textual.timer import Timer

from habits import messages
from habits.core.clock import seconds_until_boundary
from habits.core.models import ArchiveToken
from habits.core.service import HabitService
from habits.ui.screens.review import ReviewScreen
from habits.ui.screens.today import TodayScreen

RECHECK_SECONDS = 45.0


class HabitsApp(App[None]):
    CSS_PATH = "styles.tcss"
    TITLE = messages.APP_TITLE
    ENABLE_COMMAND_PALETTE = False
    MODES = {"today": TodayScreen, "review": ReviewScreen}
    DEFAULT_MODE = "today"

    def __init__(self, service: HabitService, *, recheck_seconds: float = RECHECK_SECONDS) -> None:
        super().__init__()
        self.service = service
        self.current_day = service.today()
        self.undo_stack: list[ArchiveToken] = []
        self._recheck_seconds = recheck_seconds
        self._boundary_timer: Timer | None = None

    def on_mount(self) -> None:
        # A one-shot timer for the exact boundary, plus a periodic re-check that
        # survives suspend/resume and clock changes.
        self.set_interval(self._recheck_seconds, self.check_rollover)
        self._schedule_boundary()

    def _schedule_boundary(self) -> None:
        if self._boundary_timer is not None:
            self._boundary_timer.stop()
        delay = seconds_until_boundary(self.service.clock.now(), self.service.day_start_hour)
        self._boundary_timer = self.set_timer(delay + 0.5, self.check_rollover)

    async def check_rollover(self) -> bool:
        """Swap to the new logical day if it changed. Returns True on rollover."""
        day = self.service.today()
        if day == self.current_day:
            return False
        self.current_day = day
        self.undo_stack.clear()  # past days are read-only; old archives can't be undone
        self._schedule_boundary()
        screen = self.screen
        if isinstance(screen, TodayScreen | ReviewScreen):
            await screen.reload()
        self.notify(messages.NEW_DAY)
        return True
