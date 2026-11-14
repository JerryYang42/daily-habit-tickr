-- 0001: initial schema (habits, groups, completions, meta, settings)

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE habit_groups (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  emoji        TEXT,
  sort_key     TEXT NOT NULL,
  created_day  TEXT NOT NULL,
  archived_day TEXT,
  updated_at   TEXT NOT NULL
);

CREATE TABLE habits (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  sort_key     TEXT NOT NULL,
  group_id     TEXT REFERENCES habit_groups(id),
  group_pos    INTEGER,
  created_day  TEXT NOT NULL,
  archived_day TEXT,
  updated_at   TEXT NOT NULL,
  CHECK ((group_id IS NULL) = (group_pos IS NULL))
);

CREATE TABLE completions (
  habit_id   TEXT NOT NULL REFERENCES habits(id),
  day        TEXT NOT NULL,
  state      TEXT NOT NULL CHECK (state IN ('done','cleared')),
  updated_at TEXT NOT NULL,
  device_id  TEXT NOT NULL,
  PRIMARY KEY (habit_id, day)
);

CREATE INDEX idx_completions_day ON completions(day);
CREATE INDEX idx_habits_group ON habits(group_id, group_pos);

INSERT INTO settings (key, value) VALUES ('day_start_hour', '5');
