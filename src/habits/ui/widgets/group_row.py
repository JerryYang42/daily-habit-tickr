"""A multi-count group rendered as one row: ``💧 Water ▪▪▪□□□□□ 3/8``."""

from __future__ import annotations

from textual.content import Content

from habits.core.models import TodayRow
from habits.ui.widgets.habit_row import Row

TICK = "▪"
BOX = "□"


class GroupRow(Row):
    @classmethod
    def render_row(cls, row: TodayRow) -> Content:
        label = f"{row.emoji} {row.name}" if row.emoji else row.name
        done = min(row.done, row.total)
        count_style = "$text-success" if row.complete else "$text-muted"
        return Content.assemble(
            label,
            " ",
            (TICK * done, "$text-success"),
            (BOX * (row.total - done), "$text-muted"),
            " ",
            (f"{row.done}/{row.total}", count_style),
        )
