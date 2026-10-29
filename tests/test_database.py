import sqlite3

import pytest

from devtrack.database import (
    LATEST_VERSION,
    get_connection,
    get_schema_version,
    init_db,
)

# The exact tables the MVP created, before migrations existed.
OLD_MVP_SCHEMA = """
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    tech_stack TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'in_progress', 'completed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
"""


def column_names(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_fresh_database_reaches_latest_version(conn):
    assert get_schema_version(conn) == LATEST_VERSION
    assert "priority" in column_names(conn, "tasks")
    assert "deadline" in column_names(conn, "tasks")


def test_init_db_is_idempotent(conn):
    init_db(conn)
    init_db(conn)
    assert get_schema_version(conn) == LATEST_VERSION


def test_upgrade_from_mvp_database_keeps_existing_rows(tmp_path):
    db_file = tmp_path / "old.db"
    old = sqlite3.connect(db_file)
    old.executescript(OLD_MVP_SCHEMA)
    old.execute("INSERT INTO projects (name) VALUES ('Old project')")
    old.execute("INSERT INTO tasks (project_id, title) VALUES (1, 'Old task')")
    old.commit()
    old.close()

    conn = get_connection(db_file)
    init_db(conn)

    assert get_schema_version(conn) == LATEST_VERSION
    task = conn.execute("SELECT * FROM tasks WHERE title = 'Old task'").fetchone()
    assert task is not None
    assert task["priority"] is None
    assert task["deadline"] is None
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    conn.close()


def test_priority_check_constraint_rejects_bad_values(conn):
    conn.execute("INSERT INTO projects (name) VALUES ('P')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO tasks (project_id, title, priority) VALUES (1, 'x', 9)")


def test_database_newer_than_code_is_refused(tmp_path):
    db_file = tmp_path / "future.db"
    other = sqlite3.connect(db_file)
    other.execute(f"PRAGMA user_version = {LATEST_VERSION + 1}")
    other.commit()
    other.close()

    conn = get_connection(db_file)
    with pytest.raises(sqlite3.DatabaseError, match="newer"):
        init_db(conn)
    conn.close()


def test_failed_migration_changes_nothing(tmp_path, monkeypatch):
    from devtrack import database

    db_file = tmp_path / "half.db"
    conn = get_connection(db_file)
    init_db(conn)
    version_before = get_schema_version(conn)

    # A broken migration: the first statement is fine, the second one fails.
    broken = "ALTER TABLE tasks ADD COLUMN extra TEXT; ALTER TABLE no_such_table ADD COLUMN y TEXT;"
    monkeypatch.setattr(database, "MIGRATIONS", database.MIGRATIONS + [broken])
    monkeypatch.setattr(database, "LATEST_VERSION", version_before + 1)

    with pytest.raises(sqlite3.OperationalError):
        database.init_db(conn)

    assert get_schema_version(conn) == version_before
    assert "extra" not in column_names(conn, "tasks")
    conn.close()