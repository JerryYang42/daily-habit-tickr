from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from habits import __version__
from habits.__main__ import main
from habits.db.connection import connect


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_where(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "x.db"
    assert main(["--db", str(db), "--config", str(tmp_path / "c.toml"), "--where"]) == 0
    out = capsys.readouterr().out
    assert str(db) in out and "c.toml" in out
    assert not db.exists()  # --where never creates anything


def test_env_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HABITS_DB", str(tmp_path / "env.db"))
    main(["--where"])
    assert "env.db" in capsys.readouterr().out


def test_refuses_newer_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "x.db"
    connect(db).close()
    raw = sqlite3.connect(db)
    raw.execute("PRAGMA user_version = 99")
    raw.close()
    assert main(["--db", str(db), "--config", str(tmp_path / "none.toml")]) == 2
    assert "newer" in capsys.readouterr().err


def test_bad_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text("day_start_hour = 99")
    assert main(["--db", str(tmp_path / "x.db"), "--config", str(cfg)]) == 2
    assert "day_start_hour" in capsys.readouterr().err
