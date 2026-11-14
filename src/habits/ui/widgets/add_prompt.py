"""One-line prompt for adding and renaming. Enter submits, esc cancels."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class AddPrompt(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, *, value: str = "", placeholder: str = "") -> None:
        super().__init__()
        self._title = title
        self._value = value
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt"):
            yield Label(self._title, id="prompt-title")
            yield Input(value=self._value, placeholder=self._placeholder, id="prompt-input")
            yield Label("enter to save · esc to cancel", id="prompt-hint")

    @on(Input.Submitted)
    def _submit(self, event: Input.Submitted) -> None:
        event.stop()
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
