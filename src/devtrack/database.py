"""Database connection and schema management for DevTrack."""

import sqlite3
from pathlib import Path

SCHEMA = """
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
"""


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys on and name-based row access."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create the tables if they do not exist yet (safe to call repeatedly)."""
    with conn:
        conn.executescript(SCHEMA)