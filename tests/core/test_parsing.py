from __future__ import annotations

import pytest

from habits.core.parsing import ParsedAdd, parse_add, split_emoji


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Read", ParsedAdd("Read")),
        ("  Read   a  book ", ParsedAdd("Read a book")),
        ("Water x8", ParsedAdd("Water", 8)),
        ("Water X8", ParsedAdd("Water", 8)),
        ("Water x 8", ParsedAdd("Water", 8)),
        ("💧 Water x8", ParsedAdd("Water", 8, "💧")),
        ("🧘‍♀️ Stretch x3", ParsedAdd("Stretch", 3, "🧘‍♀️")),
        ("❤️ Kind words x2", ParsedAdd("Kind words", 2, "❤️")),
        ("Pushups x50", ParsedAdd("Pushups", 50)),
        # out of range: treated as a plain habit name
        ("Pushups x51", ParsedAdd("Pushups x51")),
        ("Water x1", ParsedAdd("Water x1")),
        ("Water x0", ParsedAdd("Water x0")),
        # not a count suffix
        ("Watch Xfiles", ParsedAdd("Watch Xfiles")),
        ("x8", ParsedAdd("x8")),
        ("Box8", ParsedAdd("Box8")),
        # emoji on a plain habit stays part of the name
        ("📚 Read", ParsedAdd("📚 Read")),
        # non-emoji leading words are not emoji
        ("Été run x3", ParsedAdd("Été run", 3)),
        ("日本語 study x2", ParsedAdd("日本語 study", 2)),
    ],
)
def test_parse_add(text: str, expected: ParsedAdd) -> None:
    assert parse_add(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "\t"])
def test_blank_is_none(text: str) -> None:
    assert parse_add(text) is None


def test_split_emoji() -> None:
    assert split_emoji("💧 Water") == ("💧", "Water")
    assert split_emoji("Water") == (None, "Water")
    assert split_emoji("💧") == (None, "💧")
