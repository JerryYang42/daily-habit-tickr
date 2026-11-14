"""Read-only Review screen: yesterday, this week, and a heatmap."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.content import Content
from textual.screen import Screen
from textual.widgets import Footer, Static

from habits import messages
from habits.core import stats
from habits.core.models import DayTotal, ReviewView
from habits.ui.widgets.habit_row import make_row
from habits.ui.widgets.heatmap import Heatmap

if TYPE_CHECKING:
    from habits.ui.app import HabitsApp

BAR_WIDTH = 20


def week_line(total: DayTotal, today: str) -> Content:
    d = date.fromisoformat(total.day)
    label = "today" if total.day == today else f"{d:%a} {d.day:>2}"
    parts: list[str | tuple[str, str]] = [(f"{label:<8}", "$text-muted")]
    parts.append(f"{messages.week_cell(total.done, total.total):>9}  ")
    if total.total:
        filled = round(BAR_WIDTH * total.done / total.total)
        if total.done and not filled:
            filled = 1  # any progress is visibly something
        parts.append(("█" * filled, "$text-success"))
        parts.append(("·" * (BAR_WIDTH - filled), "$text-muted"))
    return Content.assemble(*parts)


class ReviewScreen(Screen[None]):
    BINDINGS = [
        Binding("j,down", "scroll_down", "Down", show=False),
        Binding("k,up", "scroll_up", "Up", show=False),
        Binding("tab", "today", "Today"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._reload_lock = asyncio.Lock()

    @property
    def habits_app(self) -> HabitsApp:
        return cast("HabitsApp", self.app)

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="review"):
            yield Static(messages.REVIEW_TITLE, id="heading")
            yield Static(classes="section-title", id="yesterday-title")
            yield Static(id="yesterday-summary", classes="summary")
            yield VerticalScroll(id="yesterday-rows", can_focus=False)
            yield Static(messages.WEEK_HEADING, classes="section-title")
            yield Static(id="week")
            yield Static(id="showed-up", classes="summary")
            yield Static(messages.HEATMAP_HEADING, classes="section-title")
            yield Heatmap([], id="heatmap")
        yield Footer()

    async def on_mount(self) -> None:
        await self.reload()

    async def on_screen_resume(self) -> None:
        await self.reload()

    async def reload(self) -> None:
        async with self._reload_lock:
            review = self.habits_app.service.review_view()
            self._show(review)
            rows_box = self.query_one("#yesterday-rows", VerticalScroll)
            await rows_box.remove_children()
            await rows_box.mount_all([make_row(r) for r in review.yesterday.rows])

    def _show(self, review: ReviewView) -> None:
        y = review.yesterday
        self.query_one("#yesterday-title", Static).update(
            f"{messages.YESTERDAY_HEADING} · {messages.day_heading(date.fromisoformat(y.day))}"
        )
        done, total = stats.progress(y.rows)
        self.query_one("#yesterday-summary", Static).update(messages.yesterday_summary(done, total))
        lines = [week_line(t, review.today) for t in review.week]
        self.query_one("#week", Static).update(Content("\n").join(lines))
        self.query_one("#showed-up", Static).update(
            messages.showed_up(review.showed_up_days, review.window_days)
        )
        self.query_one("#heatmap", Heatmap).set_grid(review.heatmap)

    def action_scroll_down(self) -> None:
        self.query_one("#review", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#review", VerticalScroll).scroll_up()

    def action_today(self) -> None:
        self.app.switch_mode("today")

    def action_help(self) -> None:
        from habits.ui.screens.help import HelpScreen

        self.app.push_screen(HelpScreen())
