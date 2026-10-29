"""Database connection and schema management (versioned migrations) for DevTrack."""

import sqlite3
from pathlib import Path

# Each entry is one migration. The position in the list is its version number:
# MIGRATIONS[0] is version 1, MIGRATIONS[1] is version 2, and so on.
# NEVER edit an old migration after release; add a new one at the end instead.
MIGRATIONS: list[str] = [
    # Version 1: the original MVP schema.
    """
    CREATE TABLE IF NOT EXISTS projects (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL UNIQUE,
        description TEXT,
        tech_stack  TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id   INTEGER NOT NULL
                     REFERENCES projects(id) ON DELETE CASCADE,
        title        TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'todo'
                     CHECK (status IN ('todo', 'in_progress', 'completed')),
        created_at   TEXT NOT NULL DEFAULT (datetime('now')),
        completed_at TEXT
    );
    """,
    # Version 2: task priorities (1=low, 2=medium, 3=high) and deadlines.
    """
    ALTER TABLE tasks ADD COLUMN priority INTEGER
        CHECK (priority IN (1, 2, 3));
    ALTER TABLE tasks ADD COLUMN deadline TEXT;
    """,
]

LATEST_VERSION = len(MIGRATIONS)


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys on and name-based row access."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the schema version stored in the database (0 means never migrated)."""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def init_db(conn: sqlite3.Connection) -> None:
    """Bring the database up to the latest schema, applying any missing migrations."""
    current = get_schema_version(conn)
    if current > LATEST_VERSION:
        raise sqlite3.DatabaseError(
            f"database schema version {current} is newer than this DevTrack "
            f"supports ({LATEST_VERSION}); please upgrade DevTrack"
        )
    for version, script in enumerate(MIGRATIONS, start=1):
        if version <= current:
            continue
        try:
            # BEGIN ... COMMIT makes the whole migration all-or-nothing.
            # `version` is our own integer, not user input, so the f-string is safe
            # (PRAGMA statements cannot take ? placeholders).
            conn.executescript(
                f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;"
            )
        except sqlite3.Error:
            conn.rollback()
            raise