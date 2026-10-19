"""SQLite connection and schema helpers.

The demo uses one SQLite file and plain SQL. Each request gets its own
connection, stored on ``flask.g`` and closed automatically.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from flask import current_app, g

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
SEED_FILE = Path(__file__).with_name("seed.sql")


def _connect(path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def get_db() -> sqlite3.Connection:
    """Return the request-scoped database connection."""

    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(exception=None) -> None:  # noqa: ANN001 - Flask teardown signature
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Commit on success and roll back on any error."""

    connection = get_db()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _migrate_legacy_schema(connection: sqlite3.Connection) -> None:
    """Add v0.2 columns to a database created by v0.1, if needed.

    The demo database is disposable, but this keeps an in-place upgrade from
    failing. Fresh databases already have these columns.
    """

    user_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(users)")
    }
    if "role" not in user_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'employee' "
            "CHECK (role IN ('employee', 'admin'))"
        )

    existing_kudos = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'kudos'"
    ).fetchone()
    if existing_kudos is not None:
        kudos_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(kudos)")
        }
        if "is_visible" not in kudos_columns:
            connection.execute(
                "ALTER TABLE kudos ADD COLUMN is_visible INTEGER NOT NULL DEFAULT 1 "
                "CHECK (is_visible IN (0, 1))"
            )


def init_db(path: str) -> None:
    """Create or upgrade the schema at ``path``."""

    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = _connect(str(database_path))
    try:
        existing_users = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()
        if existing_users is not None:
            _migrate_legacy_schema(connection)
        connection.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        connection.execute("PRAGMA journal_mode = WAL")
        connection.commit()
    finally:
        connection.close()


def seed_db(path: str) -> None:
    """Insert the fictional demo users if they are not already present."""

    connection = _connect(path)
    try:
        connection.executescript(SEED_FILE.read_text(encoding="utf-8"))
        connection.commit()
    finally:
        connection.close()


def init_app(app) -> None:  # noqa: ANN001 - Flask app
    """Register teardown and initialise the database for an app."""

    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db(app.config["DATABASE"])
        seed_db(app.config["DATABASE"])
        app.logger.info("SQLite database ready at %s", app.config["DATABASE"])
