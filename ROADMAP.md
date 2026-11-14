# Roadmap

Where `habits` is headed after v0.1.0. For how it works today, see [docs/design.md](docs/design.md); for what has shipped, see [CHANGELOG.md](CHANGELOG.md).

**Don't build anything here until someone explicitly asks for it.** When an item is picked up, open a GitHub issue for it, link the issue here, and keep the details in the issue. When it ships, remove it from this file and add it to the changelog.

## Now

Nothing in progress.

## Next

- [ ] **Encouragement copy**
  - Rotating warm messages when a habit is checked off
  - A "welcome back" tone after a gap in use (never "you missed N days")
  - A small celebration on a perfect day
  - A setting to turn messages down or off
  - All copy stays in `messages.py`, so it's easy to tweak
- [ ] **Help overlay** (`?`): a full, searchable list of keys. v0.1.0 has only a basic list.
- [ ] **Export** to JSON and CSV, so data is never locked in
  - Include habits, groups and completions (tombstones optional)
  - Consider a matching import
- [ ] **Categories** (for example, Health, Work, Home)
  - An optional `categories` table and a nullable `category_id` on habits and groups (needs migration `0002`)
  - Today view grouped under collapsible category headers
  - Filter by category, and per-category stats on the Review screen
  - A key to cycle or filter categories, and a way to set the category from the add/edit prompt
  - Open question: a group must belong to one category as a unit (its members inherit it)

## Later

- [ ] **Sync across devices.** The schema is already ready for it (UUIDv7 IDs, `cleared` tombstones, `updated_at`, `device_id`). The likely rule is last-write-wins per `(habit_id, day)`. Reordering already writes one row at a time.
- [ ] **A small non-interactive CLI** on the same core (for example, `habits done water` or `habits list`) for scripts and quick capture
- [ ] **A forgiving, positive-only alternative to streaks**, such as "active days this week" (only if streaks are ever wanted)
- [ ] **Backfill of the previous day**, with a gentle "forgot to tick it" flow. Out of scope by design for now: past days are read-only, and undo is limited to the same day.
