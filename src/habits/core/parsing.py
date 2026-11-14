"""Parse the one-line add prompt: ``Read`` or ``💧 Water x8``."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from habits.core.models import MAX_GROUP_SIZE, MIN_GROUP_SIZE

_COUNT_RE = re.compile(r"^(?P<body>.*\S)\s+[xX×]\s*(?P<count>\d+)$")
_EMOJI_JOINERS = {"‍", "️", "︎", "⃣"}


@dataclass(frozen=True, slots=True)
class ParsedAdd:
    name: str
    count: int | None = None  # None for a plain habit
    emoji: str | None = None

    @property
    def is_group(self) -> bool:
        return self.count is not None


def _is_emoji_token(token: str) -> bool:
    if not token:
        return False
    has_symbol = False
    for ch in token:
        if ch in _EMOJI_JOINERS:
            continue
        if ch.isascii() or ch.isalnum():
            return False
        cat = unicodedata.category(ch)
        if cat in ("So", "Sk"):
            has_symbol = True
        elif not cat.startswith("M"):  # allow combining marks / skin-tone modifiers
            return False
    return has_symbol


def split_emoji(text: str) -> tuple[str | None, str]:
    """Split an optional leading emoji token from a name."""
    text = text.strip()
    head, _, rest = text.partition(" ")
    rest = rest.strip()
    if rest and _is_emoji_token(head):
        return head, rest
    return None, text


def parse_add(text: str) -> ParsedAdd | None:
    """Return what to create, or None when the input is blank."""
    text = " ".join(text.split())
    if not text:
        return None
    m = _COUNT_RE.match(text)
    if m:
        count = int(m.group("count"))
        if MIN_GROUP_SIZE <= count <= MAX_GROUP_SIZE:
            emoji, name = split_emoji(m.group("body"))
            return ParsedAdd(name=name, count=count, emoji=emoji)
    return ParsedAdd(name=text)
