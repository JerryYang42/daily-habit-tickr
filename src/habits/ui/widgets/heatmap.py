"""GitHub-style heatmap drawn with block characters. Greens only, never red."""

from __future__ import annotations

from datetime import date

from textual.content import Content
from textual.widgets import Static

from habits import messages
from habits.core.models import HeatmapCell

CELL = "■"
# index = shade level 0..4. Level 0 = active habits but nothing ticked: a quiet grey.
DARK = ("#3a3f47", "#0e4429", "#006d32", "#26a641", "#39d353")
LIGHT = ("#dfe3e8", "#9be9a8", "#40c463", "#30a14e", "#216e39")
WEEKDAY_LABELS = ("Mon", "", "Wed", "", "Fri", "", "")


class Heatmap(Static):
    def __init__(self, grid: list[list[HeatmapCell | None]], **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.grid = grid

    def set_grid(self, grid: list[list[HeatmapCell | None]]) -> None:
        self.grid = grid
        self.refresh()

    def _palette(self) -> tuple[str, ...]:
        try:
            dark = self.app.current_theme.dark
        except Exception:  # pragma: no cover - no app / theme yet
            dark = True
        return DARK if dark else LIGHT

    def render(self) -> Content:
        palette = self._palette()
        parts: list[str | tuple[str, str]] = []

        # Month labels above the first column of each month.
        months = ["    "]
        last_month = None
        pending = ""
        for column in self.grid:
            first = next((c for c in column if c is not None), None)
            label = "  "
            if first is not None:
                m = date.fromisoformat(first.day).month
                if m != last_month:
                    pending = date.fromisoformat(first.day).strftime("%b")
                    last_month = m
            if pending:
                label, pending = (pending + " ")[:2], pending[2:]
            months.append(label)
        parts.append(("".join(months).rstrip() + "\n", "$text-muted"))

        for weekday in range(7):
            parts.append((f"{WEEKDAY_LABELS[weekday]:<4}", "$text-muted"))
            for column in self.grid:
                cell = column[weekday]
                if cell is None or cell.ratio is None:
                    parts.append("  ")
                else:
                    parts.append((CELL + " ", palette[cell.level]))
            parts.append("\n")

        parts.append((f"\n    {messages.HEATMAP_LESS} ", "$text-muted"))
        for color in palette:
            parts.append((CELL + " ", color))
        parts.append((messages.HEATMAP_MORE, "$text-muted"))
        return Content.assemble(*parts)
