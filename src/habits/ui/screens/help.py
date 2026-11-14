"""Basic keybinding list (a richer overlay is on the roadmap)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from habits import messages


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,question_mark,q", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        width = max(len(k) for k, _ in messages.HELP_ROWS) + 2
        body = Content("\n").join(
            Content.assemble((f"{key:<{width}}", "bold $text-accent"), desc)
            for key, desc in messages.HELP_ROWS
        )
        with Vertical(id="help"):
            yield Label(messages.HELP_TITLE, id="help-title")
            yield Static(body)
            yield Label(messages.HELP_FOOTER, id="help-hint")

    def action_close(self) -> None:
        self.dismiss(None)
