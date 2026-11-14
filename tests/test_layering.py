"""Dependency rules: ui -> core <- db. Core never imports textual or sqlite3; UI never SQL."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "habits"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def files(sub: str) -> list[Path]:
    return sorted((SRC / sub).rglob("*.py"))


@pytest.mark.parametrize("path", files("core"), ids=lambda p: p.name)
def test_core_is_pure(path: Path) -> None:
    bad = {
        m
        for m in imported_modules(path)
        if m.split(".")[0] in {"textual", "sqlite3", "rich"}
        or m.startswith("habits.db")
        or m.startswith("habits.ui")
    }
    assert not bad, f"{path} imports {bad}"


@pytest.mark.parametrize("path", files("db"), ids=lambda p: p.name)
def test_db_does_not_import_ui(path: Path) -> None:
    bad = {m for m in imported_modules(path) if m.startswith(("habits.ui", "textual"))}
    assert not bad, f"{path} imports {bad}"
