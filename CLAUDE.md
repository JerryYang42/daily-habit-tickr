# CLAUDE.md

`habits` is a local-first terminal habit tracker (Python 3.12+, Textual, SQLite).

## Docs

- [docs/design.md](docs/design.md): how it works and why (behavior, data model, decisions). **Read it before changing behavior.**
- [ROADMAP.md](ROADMAP.md): future work. **Don't implement roadmap items unless explicitly asked.**
- [CHANGELOG.md](CHANGELOG.md): add user-visible changes under `[Unreleased]`.
- [README.md](README.md): install and usage, for users.

When behavior changes, update `docs/design.md` (and the README if users would notice) in the same change.

## Commands

```sh
uv sync                     # dev environment
uv run habits               # run from source (use --db /tmp/x.db to avoid touching real data)
uv run pytest -q            # all tests
uv run ruff check . && uv run ruff format --check . && uv run mypy   # the other gates
uv run pytest tests/ui/test_snapshots.py --snapshot-update            # only after an intended UI change
```

All four gates (ruff check, ruff format, mypy strict, pytest) must pass before committing.

## Rules that are easy to break

- **Layering:** `ui → core ← db`. `habits.core` must not import `textual`, `rich`, `sqlite3`, `habits.db` or `habits.ui`. SQL lives only in `habits/db/repo.py` (and in migrations). `tests/test_layering.py` enforces this.
- **Tone:** all user-facing text goes in `src/habits/messages.py`. Never use red/`$error`, "missed", "failed", streaks or negative counts.
- **History:** never delete completion rows; un-ticking writes `state='cleared'`. Only write to the current logical day (`service.today()`). Archive instead of delete.
- **Days:** compute logical days once, at write time, with `core.clock.logical_day`. Never derive them from stored timestamps. Use the injected `Clock`, never `datetime.now()`, in core.
- **Transactions:** anything that writes several rows goes in `repo.transaction()`.
- **Schema changes:** add `src/habits/db/migrations/NNNN_name.sql` (the next number, no gaps). Never edit an existing migration.
- **Tests:** use the `service` / `clock` fixtures in `tests/conftest.py` (an in-memory DB and a `ManualClock` set to Sat 2026-11-14 12:00 America/New_York).
- **Textual gotchas:** don't name methods `_render`, `_classes` or `action_toggle` (they clash with Textual internals; mypy catches this). Bind `tab` on screens, not on the app.

## Commits

Small conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). Branch from `main`; don't commit to it directly.
