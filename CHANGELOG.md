# Changelog

All notable changes to this project are listed here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- Reorganized the project docs: `PLAN.md` became [docs/design.md](docs/design.md) (rewritten to match the shipped code), [ROADMAP.md](ROADMAP.md) is now grouped as Now / Next / Later, and this changelog and `CLAUDE.md` were added.

## [0.1.0] - 2026-11-14

First release.

### Added
- **Today screen:** daily yes/no habits, toggled with `space` / `enter`, and the cursor moves to the next row once something is done.
- **Groups:** `💧 Water x8` makes one row of 8 boxes. `space` ticks the next box, `backspace` clears the last one, and `+` / `-` resize the group (2 to 50).
- **Logical days** start at 5:00 AM, and the app switches to the new day while it's open.
- **Managing habits:** add (`a`), rename (`e`), archive (`d`) with undo (`u`) and no confirmation dialogs, and reorder (`J` / `K`).
- **Review screen** (`tab`): yesterday's results, the last 7 days, "X of the last 14 days", and a 12-week heatmap where partial days get lighter shades.
- A progress line where every tick counts, with copy that is always neutral or warm (no streaks, no red, no "missed").
- Local SQLite storage in the user data directory, with a schema that's ready for sync (UUIDv7, tombstones, `updated_at`, `device_id`).
- An optional `config.toml` (`day_start_hour`, `timezone`), plus the `--db`, `--config` and `--where` options and the `HABITS_DB` / `HABITS_CONFIG` environment variables.
- Packaging with `uv tool install`, and CI on Ubuntu and macOS with Python 3.12–3.14.

[Unreleased]: https://github.com/JerryYang42/daily-habit-tickr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/JerryYang42/daily-habit-tickr/releases/tag/v0.1.0
