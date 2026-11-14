# Roadmap

Things deliberately deferred. The core app (milestones M1 to M5 in [PLAN.md](PLAN.md)) ships first; these come after. Do not implement anything here unless explicitly asked.

## Polish and quality of life

- [ ] **Encouragement copy**
  - Rotating warm messages when a habit is checked off
  - A "welcome back" tone after a gap in usage (never "you missed N days")
  - A small celebration on a perfect day
  - A setting to turn messages down or off
  - All copy lives in `messages.py`; keep it easy to tweak
- [ ] **Help overlay** (`?`): a full, searchable list of keybindings (M3 ships only a basic list)
- [ ] **Export** to JSON and CSV so data is never locked in
  - Include habits, groups, and completions (with tombstones optional)
  - Also consider a matching import

## Organization

- [ ] **Categories for habits** (e.g. Health, Work, Home)
  - Optional `categories` table and nullable `category_id` on habits and groups
  - Today view grouped under collapsible category headers
  - Filter by category; per-category stats in the Review screen
  - Keyboard: a key to cycle or filter category, and a way to set the category from the add/edit prompt
  - Open design question: a multi-count group must belong to one category as a unit (members inherit it)

## Ideas for later

- [ ] **Sync across devices.** The schema is already sync-ready: UUIDv7 IDs, tombstones (`state='cleared'`), `updated_at`, and `device_id`. Likely last-write-wins per `(habit_id, day)`.
- [ ] **Tiny non-interactive CLI** sharing the same core (e.g. `habits done water`, `habits list`) for scripting and quick capture
- [ ] **Forgiving, positive-only streak alternative**, such as "active days this week" (only if streaks are ever wanted)
- [ ] **Backfill of the previous day** with a gentle "forgot to tick it" flow (currently out of scope by design)
