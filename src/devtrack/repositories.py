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


def add_task(conn: sqlite3.Connection, project_id: int, title: str) -> int:
    "Insert  a task (status defaults to 'todo) and return its new id."""
    with conn:
        cursor = conn.execute(
            "INSERT INTO tasks(project_id, title) VALUES (?,?)",
             (project_id, title),
        )
    return cursor.lastrowid

def list_tasks(
    conn: sqlite3.Connection, project_id: int, status: str | None = None 
    ) -> list[sqlite3.Row]:
    """Return a project's tasks, ordered by id, optioanlly filtered by status."""
    if status is None:
        return conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM tasks where project_id = ? AND status = ? ORDER BY id",
        (project_id, status),
     ).fetchall()
    return conn.execute(
        "SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY id",
        (project_id, status),
    ).fetchall()


   