"""The Today screen: the list you tick things off on."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

from habits import messages
from habits.core import stats
from habits.core.models import DayView, TodayRow
from habits.ui.widgets.add_prompt import AddPrompt
from habits.ui.widgets.habit_row import Row, make_row

if TYPE_CHECKING:
    from habits.core.service import HabitService
    from habits.ui.app import HabitsApp

ROW_ACTIONS = {"tick", "clear", "rename", "archive", "move_down", "move_up"}
GROUP_ACTIONS = {"grow", "shrink"}


class RowList(VerticalScroll, can_focus=False):
    """Scrollable list of rows. Not focusable: the screen owns all keys."""


class TodayScreen(Screen[None]):
    BINDINGS = [
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up", "cursor_up", "Up", show=False),
        Binding("g,home", "cursor_first", "First", show=False),
        Binding("G,shift+g,end", "cursor_last", "Last", show=False),
        Binding("space,enter", "tick", "Tick", key_display="space"),
        Binding("backspace", "clear", "Clear", show=False),
        Binding("a", "add", "Add"),
        Binding("e", "rename", "Rename"),
        Binding("d", "archive", "Archive"),
        Binding("u", "undo", "Undo"),
        Binding("plus", "grow", "Grow", key_display="+"),
        Binding("minus", "shrink", "Shrink", key_display="-"),
        Binding("J,shift+j", "move_down", "Move ↓", show=False),
        Binding("K,shift+k", "move_up", "Move ↑", show=False),
        Binding("tab", "review", "Review"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.view = DayView(day="")
        self.cursor = 0
        self._reload_lock = asyncio.Lock()

    # ---- plumbing -------------------------------------------------------------

    @property
    def habits_app(self) -> HabitsApp:
        return cast("HabitsApp", self.app)

    @property
    def service(self) -> HabitService:
        return self.habits_app.service

    def compose(self) -> ComposeResult:
        yield Static(id="heading")
        yield Static(id="progress")
        yield RowList(id="rows")
        yield Static(f"{messages.EMPTY_TODAY}\n{messages.EMPTY_HINT}", id="empty")
        yield Footer()

    async def on_mount(self) -> None:
        await self.reload()

    async def on_screen_resume(self) -> None:
        await self.reload()

    @property
    def current(self) -> TodayRow | None:
        rows = self.view.rows
        return rows[self.cursor] if 0 <= self.cursor < len(rows) else None

    def row_widgets(self) -> list[Row]:
        return list(self.query_one("#rows", RowList).query(Row))

    async def reload(self, focus_id: str | None = None) -> None:
        """Re-read today's rows. Keep the cursor on the same row (by id) when possible."""
        async with self._reload_lock:  # reloads can overlap (e.g. modal dismiss + resume)
            await self._reload(focus_id)

    async def _reload(self, focus_id: str | None) -> None:
        keep = focus_id or (self.current.id if self.current else None)
        old_index = self.cursor
        self.view = self.service.today_view()
        rows = self.view.rows

        ids = [r.id for r in rows]
        if keep in ids:
            self.cursor = ids.index(keep)
        else:
            self.cursor = min(old_index, len(rows) - 1) if rows else 0

        container = self.query_one("#rows", RowList)
        widgets = self.row_widgets()
        if [w.row.id for w in widgets] == ids:
            for w, r in zip(widgets, rows, strict=True):
                w.set_row(r)
        else:
            await container.remove_children()
            await container.mount_all(
                [make_row(r, cursor=(i == self.cursor)) for i, r in enumerate(rows)]
            )
        self._paint_cursor()
        self._update_header()

    def _update_header(self) -> None:
        heading = messages.day_heading(date.fromisoformat(self.view.day)) if self.view.day else ""
        self.query_one("#heading", Static).update(heading)
        done, total = stats.progress(self.view.rows)
        self.query_one("#progress", Static).update(messages.progress_line(done, total))
        empty = not self.view.rows
        self.query_one("#empty", Static).display = empty
        self.query_one("#rows", RowList).display = not empty
        self.refresh_bindings()

    def _paint_cursor(self) -> None:
        widgets = self.row_widgets()
        for i, w in enumerate(widgets):
            w.set_cursor(i == self.cursor)
        if 0 <= self.cursor < len(widgets):
            self.query_one("#rows", RowList).scroll_to_widget(widgets[self.cursor], animate=False)
        self.refresh_bindings()

    def _move_cursor(self, index: int) -> None:
        if not self.view.rows:
            return
        self.cursor = max(0, min(index, len(self.view.rows) - 1))
        self._paint_cursor()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        row = self.current
        if action in ROW_ACTIONS:
            return row is not None
        if action in GROUP_ACTIONS:
            return row is not None and row.is_group
        return True

    # ---- navigation -------------------------------------------------------------

    def action_cursor_down(self) -> None:
        self._move_cursor(self.cursor + 1)

    def action_cursor_up(self) -> None:
        self._move_cursor(self.cursor - 1)

    def action_cursor_first(self) -> None:
        self._move_cursor(0)

    def action_cursor_last(self) -> None:
        self._move_cursor(len(self.view.rows) - 1)

    def action_review(self) -> None:
        self.app.switch_mode("review")

    def action_help(self) -> None:
        from habits.ui.screens.help import HelpScreen

        self.app.push_screen(HelpScreen())

    # ---- ticking --------------------------------------------------------------------

    async def action_tick(self) -> None:
        row = self.current
        if row is None:
            return
        if row.is_group:
            self.service.tick_group(row.id)
        else:
            self.service.toggle_habit(row.id)
        await self.reload(row.id)
        after = self.current
        # Advance only when the row just became fully done (never on un-toggle).
        if after is not None and after.id == row.id and after.complete and not row.complete:
            self._move_cursor(self.cursor + 1)

    async def action_clear(self) -> None:
        row = self.current
        if row is None:
            return
        if row.is_group:
            self.service.clear_last(row.id)
        else:
            self.service.clear_habit(row.id)
        await self.reload(row.id)

    # ---- managing ---------------------------------------------------------------------

    def action_add(self) -> None:
        async def done(text: str | None) -> None:
            if not text:
                return
            new_id = self.service.add(text)
            if new_id is not None:
                await self.reload(new_id)

        self.app.push_screen(
            AddPrompt(messages.ADD_TITLE, placeholder=messages.ADD_PLACEHOLDER), done
        )

    def action_rename(self) -> None:
        row = self.current
        if row is None:
            return
        value = f"{row.emoji} {row.name}" if row.emoji else row.name

        async def done(text: str | None) -> None:
            if text and self.service.rename(row.id, text):
                await self.reload(row.id)

        self.app.push_screen(AddPrompt(messages.RENAME_TITLE, value=value), done)

    async def action_archive(self) -> None:
        row = self.current
        if row is None:
            return
        token = self.service.archive(row.id)
        if token is None:
            return
        self.habits_app.undo_stack.append(token)
        await self.reload()
        self.notify(messages.archived(token.name))

    async def action_undo(self) -> None:
        stack = self.habits_app.undo_stack
        while stack:
            token = stack.pop()
            if self.service.restore(token):
                await self.reload(token.id)
                self.notify(messages.restored(token.name))
                return
        self.notify(messages.NOTHING_TO_UNDO)

    async def action_grow(self) -> None:
        row = self.current
        if row is None or not row.is_group:
            return
        if self.service.grow_group(row.id):
            await self.reload(row.id)
        else:
            self.notify(messages.GROUP_AT_MAX)

    async def action_shrink(self) -> None:
        row = self.current
        if row is None or not row.is_group:
            return
        if self.service.shrink_group(row.id):
            await self.reload(row.id)
        else:
            self.notify(messages.GROUP_AT_MIN)

    async def _move(self, delta: int) -> None:
        row = self.current
        if row is not None and self.service.move(row.id, delta):
            await self.reload(row.id)

    async def action_move_down(self) -> None:
        await self._move(+1)

    async def action_move_up(self) -> None:
        await self._move(-1)
