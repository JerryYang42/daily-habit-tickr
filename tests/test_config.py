from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from habits.config import Config, ConfigError, load_config


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "nope.toml") == Config()


def test_reads_values(tmp_path: Path) -> None:
    cfg = load_config(write(tmp_path, 'day_start_hour = 4\ntimezone = "Asia/Tokyo"\n'))
    assert cfg == Config(day_start_hour=4, timezone=ZoneInfo("Asia/Tokyo"))


@pytest.mark.parametrize(
    "text",
    [
        "day_start_hour = 24",
        "day_start_hour = -1",
        'day_start_hour = "5"',
        "day_start_hour = true",
        'timezone = "Mars/Olympus"',
        "timezone = 5",
        "not toml at all [",
    ],
)
def test_rejects_bad_values(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, text))
