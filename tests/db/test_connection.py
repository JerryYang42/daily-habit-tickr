from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from habits.db.connection import NewerSchemaError, connect, latest_version, migrate


def tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','index')")
    return {r[0] for r in rows}


def test_fresh_db_has_full_schema(conn: sqlite3.Connection) -> None:
    assert {
        "meta",
        "settings",
        "habit_groups",
        "habits",
        "completions",
        "idx_completions_day",
        "idx_habits_group",
    } <= tables(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == latest_version() == 1
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    setting = conn.execute("SELECT value FROM settings WHERE key='day_start_hour'").fetchone()
    assert setting[0] == "5"


def test_file_db_uses_wal_and_keeps_device_id(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "habits.db"
    c1 = connect(path)
    assert c1.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    device = c1.execute("SELECT value FROM meta WHERE key='device_id'").fetchone()[0]
    c1.close()
    c2 = connect(path)
    assert c2.execute("SELECT value FROM meta WHERE key='device_id'").fetchone()[0] == device
    c2.close()


def test_migrate_is_idempotent(conn: sqlite3.Connection) -> None:
    assert migrate(conn) == latest_version()


def test_refuses_newer_schema(tmp_path: Path) -> None:
    path = tmp_path / "habits.db"
    connect(path).close()
    raw = sqlite3.connect(path)
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    with pytest.raises(NewerSchemaError):
        connect(path)


def test_group_pos_check_constraint(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO habits (id, name, sort_key, group_id, group_pos, created_day, updated_at)"
            " VALUES ('h', 'x', 'V', NULL, 1, '2026-01-01', 't')"
        )


def test_completion_state_check(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO habits (id, name, sort_key, created_day, updated_at)"
        " VALUES ('h', 'x', 'V', '2026-01-01', 't')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO completions VALUES ('h', '2026-01-01', 'missed', 't', 'd')")
