PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    department  TEXT,
    role        TEXT    NOT NULL DEFAULT 'employee'
                CHECK (role IN ('employee', 'admin')),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS kudos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    giver_id      INTEGER NOT NULL REFERENCES users(id),
    recipient_id  INTEGER NOT NULL REFERENCES users(id),
    message       TEXT    NOT NULL
                  CHECK (length(trim(message)) BETWEEN 1 AND 500),
    is_visible    INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0, 1)),
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (giver_id <> recipient_id)
);

-- Full ordering index: employee feed and administrator list.
CREATE INDEX IF NOT EXISTS idx_kudos_created_at
    ON kudos (created_at DESC, id DESC);

-- Partial index: the employee feed reads only visible kudos.
CREATE INDEX IF NOT EXISTS idx_kudos_visible_created_at
    ON kudos (created_at DESC, id DESC)
    WHERE is_visible = 1;
