"""A single row in a day list. Plain habits render as ``[x] Read``."""

from __future__ import annotations

from textual.content import Content
from textual.widgets import Static

from habits.core.models import TodayRow


class Row(Static):
    """Base class for list rows. Holds the TodayRow it renders."""

    def __init__(self, row: TodayRow, *, cursor: bool = False) -> None:
        super().__init__(self.render_row(row), classes=self._row_classes(row, cursor))
        self.row = row

    @staticmethod
    def _row_classes(row: TodayRow, cursor: bool) -> str:
        names = ["row"]
        if row.complete:
            names.append("-done")
        if cursor:
            names.append("-cursor")
        return " ".join(names)

    def set_row(self, row: TodayRow) -> None:
        self.row = row
        self.set_class(row.complete, "-done")
        self.update(self.render_row(row))

    def set_cursor(self, on: bool) -> None:
        self.set_class(on, "-cursor")

    @classmethod
    def render_row(cls, row: TodayRow) -> Content:
        raise NotImplementedError


class HabitRow(Row):
    @classmethod
    def render_row(cls, row: TodayRow) -> Content:
        if row.complete:
            return Content.assemble(("[x]", "$text-success"), " ", row.name)
        return Content.assemble(("[ ]", "$text-muted"), " ", row.name)


def make_row(row: TodayRow, *, cursor: bool = False) -> Row:
    from habits.ui.widgets.group_row import GroupRow

    cls: type[Row] = GroupRow if row.is_group else HabitRow
    return cls(row, cursor=cursor)
