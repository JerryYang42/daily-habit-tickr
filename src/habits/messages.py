"""All user-facing copy in one place.

Tone rules: neutral or warm, never shaming. No "missed", "failed", or negative counts.
"""

from __future__ import annotations

from datetime import date

from habits.core.models import MAX_GROUP_SIZE, MIN_GROUP_SIZE

APP_TITLE = "habits"

# ---- Today -------------------------------------------------------------------------

EMPTY_TODAY = "Nothing here yet. Press [b]a[/b] to add your first habit."
EMPTY_HINT = "Tip: [b]💧 Water x8[/b] makes a group of 8 boxes."


def progress_line(done: int, total: int) -> str:
    if total == 0:
        return "A blank page, full of possibility"
    if done == 0:
        return "Fresh day, ready when you are"
    if done >= total:
        return f"All {total} done today. Lovely."
    return f"{done} of {total} today"


def day_heading(day: date) -> str:
    return f"{day:%A}, {day.day} {day:%B}"


ADD_TITLE = "New habit"
ADD_PLACEHOLDER = "Read  ·  or  💧 Water x8  for a group"
RENAME_TITLE = "Rename"


def added(name: str) -> str:
    return f"Added “{name}”"


def archived(name: str) -> str:
    return f"Archived “{name}”. Press u to undo."


def restored(name: str) -> str:
    return f"Restored “{name}”"


NOTHING_TO_UNDO = "Nothing to undo"
GROUP_AT_MIN = f"A group keeps at least {MIN_GROUP_SIZE} boxes"
GROUP_AT_MAX = f"A group can hold up to {MAX_GROUP_SIZE} boxes"
NEW_DAY = "New day, fresh start ☀️"

# ---- Review --------------------------------------------------------------------------

REVIEW_TITLE = "Review"
YESTERDAY_HEADING = "Yesterday"
WEEK_HEADING = "This week"
HEATMAP_HEADING = "Last 12 weeks"


def yesterday_summary(done: int, total: int) -> str:
    if total == 0:
        return "Nothing was on the list yesterday"
    if done == 0:
        return "Yesterday was a rest day. Today is a fresh one."
    if done >= total:
        return f"You did all {total} yesterday"
    return f"You did {done} of {total} yesterday"


def week_cell(done: int, total: int) -> str:
    if total == 0:
        return "—"
    return f"{done} of {total}"


def showed_up(days: int, window: int) -> str:
    if days == 0:
        return f"Any day is a good day to begin. Here's to the next {window}."
    if days == 1:
        return f"You checked something off on 1 of the last {window} days"
    return f"You checked something off on {days} of the last {window} days"


HEATMAP_LESS = "less"
HEATMAP_MORE = "more"

# ---- Help ------------------------------------------------------------------------------

HELP_TITLE = "Keys"
HELP_ROWS: list[tuple[str, str]] = [
    ("j / ↓, k / ↑", "Move"),
    ("g / G", "First / last row"),
    ("space, enter", "Tick a habit, or the next box in a group"),
    ("backspace", "Clear the last ticked box"),
    ("a", "Add a habit (Name x8 makes a group)"),
    ("e", "Rename"),
    ("d", "Archive"),
    ("u", "Undo the last archive"),
    ("+ / -", "Grow / shrink a group"),
    ("J / K", "Move row down / up"),
    ("tab", "Switch Today ↔ Review"),
    ("?", "This help"),
    ("q", "Quit"),
]
HELP_FOOTER = "Press esc or ? to close"
