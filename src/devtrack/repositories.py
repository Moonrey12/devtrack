"""SQL access for projects. This module only talks to the database."""

import sqlite3
from datetime import datetime

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


def add_task(
    conn: sqlite3.Connection,
    project_id: int,
    title: str,
    priority: int | None = None,
    deadline: str | None = None,
) -> int:
    """Insert a task (status defaults to 'todo') and return its new id."""
    with conn:
        cursor = conn.execute(
            "INSERT INTO tasks (project_id, title, priority, deadline) "
            "VALUES (?, ?, ?, ?)",
            (project_id, title, priority, deadline),
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

def get_task(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row | None:
    """Return one task by id, or None if it does not exist."""
    return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def update_task_status(conn: sqlite3.Connection, task_id: int, status: str) -> bool:
    """Set a task's status; return True if a task was updated, False if not found."""
    with conn:
        if status == "completed":
            cursor = conn.execute(
                "UPDATE tasks SET status = ?, completed_at = datetime('now') "
                "WHERE id = ?",
                (status, task_id),
            )
        else:
            cursor = conn.execute(
                "UPDATE tasks SET status = ?, completed_at = NULL WHERE id = ?",
                (status, task_id),
            )
    return cursor.rowcount > 0


def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    """Delete a task; return True if a task was deleted, False if not found."""
    with conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cursor.rowcount > 0

def set_task_priority_deadline(
    conn: sqlite3.Connection,
    task_id: int,
    priority: int | None,
    deadline: str | None,
) -> bool:
    """Set a task's priority and deadline (None clears them); True if the task exists."""
    with conn:
        cursor = conn.execute(
            "UPDATE tasks SET priority = ?, deadline = ? WHERE id = ?",
            (priority, deadline, task_id),
        )
    return cursor.rowcount > 0


def _escape_like(text: str) -> str:
    """Escape LIKE wildcards (% and _) so the user's text is matched literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_tasks(
        conn: sqlite3.Connection, text: str | None = None
) -> list[sqlite3.Row]:
    """Return tasks from all projects (with project_name), optionally title-filtered."""
    query = (
        "SELECT tasks.*, projects.name AS project_name "
        "FROM tasks JOIN projects ON projects.id = tasks.project_id"
        )
    params: list[object] = []
    if text:
        query += " WHERE tasks.title LIKE ? ESCAPE '\\'"
        params.append(f"%{_escape_like(text)}%")
    query += " ORDER BY tasks.id"
    return conn.execute(query, params).fetchall()
        
   