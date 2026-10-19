"""SQL access for projects. This module only talks to the database."""

import sqlite3


def add_project(
    conn: sqlite3.Connection,
    name: str,
    description: str | None,
    tech_stack: str | None,
) -> int:
    """Insert a project and return its new id (raises IntegrityError on duplicate name)."""
    with conn:
        cursor = conn.execute(
            "INSERT INTO projects (name, description, tech_stack) VALUES (?, ?, ?)",
            (name, description, tech_stack),
        )
    return cursor.lastrowid


def list_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return all projects ordered by id."""
    return conn.execute("SELECT * FROM projects ORDER BY id").fetchall()


def get_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    """Return one project by id, or None if it does not exist."""
    return conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()