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


# ORDER BY cannot take ? placeholders, so the allowed sort orders are a fixed
# allow-list: the user picks a KEY, and the SQL text comes only from this dictionary.
# "IS NULL" sorts rows with no value after rows that have one.
SORT_ORDERS = {
    "id": "tasks.id",
    "deadline": "tasks.deadline IS NULL, tasks.deadline ASC, tasks.id",
    "priority": "tasks.priority IS NULL, tasks.priority DESC, tasks.id",
    "title": "tasks.title COLLATE NOCASE, tasks.id",
}
SORT_CHOICES = list(SORT_ORDERS)


def search_tasks(
    conn: sqlite3.Connection,
    text: str | None = None,
    *,
    project_id: int | None = None,
    status: str | None = None,
    priority: int | None = None,
    due_by: str | None = None,
    overdue: bool = False,
    today: str | None = None,
    sort: str = "id",
) -> list[sqlite3.Row]:
    """Search tasks across projects; every filter is optional and filters combine with AND."""
    if overdue and today is None:
        raise ValueError("today (YYYY-MM-DD) is required when overdue=True")
    if sort not in SORT_ORDERS:
        raise ValueError(f"sort must be one of: {', '.join(SORT_CHOICES)}")

    query = (
        "SELECT tasks.*, projects.name AS project_name "
        "FROM tasks JOIN projects ON projects.id = tasks.project_id"
    )
    conditions: list[str] = []  # fixed SQL pieces that WE wrote
    params: list[object] = []  # the user's values, kept separate from the SQL text

    if text:
        conditions.append("tasks.title LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(text)}%")
    if project_id is not None:
        conditions.append("tasks.project_id = ?")
        params.append(project_id)
    if status is not None:
        conditions.append("tasks.status = ?")
        params.append(status)
    if priority is not None:
        conditions.append("tasks.priority = ?")
        params.append(priority)
    if due_by is not None:
        conditions.append("tasks.deadline <= ?")
        params.append(due_by)
    if overdue:
        conditions.append("tasks.deadline < ?")
        params.append(today)
        conditions.append("tasks.status != 'completed'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY " + SORT_ORDERS[sort]
    return conn.execute(query, params).fetchall()


def start_session(
    conn: sqlite3.Connection,
    project_id: int,
    task_id: int | None,
    started_at: str,
) -> int:
    """Insert a running session and return its id (IntegrityError if one is already active)."""
    with conn:
        cursor = conn.execute(
            "INSERT INTO sessions (project_id, task_id, started_at) VALUES (?, ?, ?)",
            (project_id, task_id, started_at),
        )
    return cursor.lastrowid


def get_active_session(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """Return the running session (with project name and task title), or None."""
    return conn.execute(
        "SELECT sessions.*, projects.name AS project_name, tasks.title AS task_title "
        "FROM sessions "
        "JOIN projects ON projects.id = sessions.project_id "
        "LEFT JOIN tasks ON tasks.id = sessions.task_id "
        "WHERE sessions.ended_at IS NULL"
    ).fetchone()


def stop_session(conn: sqlite3.Connection, session_id: int, ended_at: str) -> bool:
    """End a RUNNING session; True if it was stopped, False if missing or already stopped."""
    with conn:
        cursor = conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (ended_at, session_id),
        )
    return cursor.rowcount > 0


def list_sessions(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    """Return the most recent sessions first, with project name and task title."""
    return conn.execute(
        "SELECT sessions.*, projects.name AS project_name, tasks.title AS task_title "
        "FROM sessions "
        "JOIN projects ON projects.id = sessions.project_id "
        "LEFT JOIN tasks ON tasks.id = sessions.task_id "
        "ORDER BY sessions.started_at DESC, sessions.id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def sessions_overlapping(
    conn: sqlite3.Connection, window_start: str, window_end: str
) -> list[sqlite3.Row]:
    """Return sessions that overlap the half-open UTC window [start, end) (ISO text times)."""
    return conn.execute(
        "SELECT sessions.*, projects.name AS project_name "
        "FROM sessions JOIN projects ON projects.id = sessions.project_id "
        "WHERE sessions.started_at < ? "
        "AND (sessions.ended_at IS NULL OR sessions.ended_at > ?) "
        "ORDER BY sessions.started_at, sessions.id",
        (window_end, window_start),
    ).fetchall()


def tasks_completed_between(
    conn: sqlite3.Connection, start_text: str, end_text: str
) -> list[sqlite3.Row]:
    """Return tasks completed in [start, end); times are SQLite-style 'YYYY-MM-DD HH:MM:SS' UTC."""
    return conn.execute(
        "SELECT tasks.*, projects.name AS project_name "
        "FROM tasks JOIN projects ON projects.id = tasks.project_id "
        "WHERE tasks.status = 'completed' "
        "AND tasks.completed_at >= ? AND tasks.completed_at < ? "
        "ORDER BY tasks.completed_at, tasks.id",
        (start_text, end_text),
    ).fetchall()


def count_tasks_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    """Return how many tasks have each status (statuses with no tasks are 0)."""
    counts = {"todo": 0, "in_progress": 0, "completed": 0}
    for row in conn.execute("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"):
        counts[row["status"]] = row["n"]
    return counts


def task_counts_by_project(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return each project with its total and completed task counts (projects with 0 tasks too)."""
    return conn.execute(
        "SELECT projects.id, projects.name, "
        "COUNT(tasks.id) AS total, "
        "SUM(CASE WHEN tasks.status = 'completed' THEN 1 ELSE 0 END) AS completed "
        "FROM projects LEFT JOIN tasks ON tasks.project_id = projects.id "
        "GROUP BY projects.id, projects.name "
        "ORDER BY projects.name COLLATE NOCASE, projects.id"
    ).fetchall()


def count_overdue_tasks(conn: sqlite3.Connection, today: str) -> int:
    """Count unfinished tasks whose deadline (YYYY-MM-DD) is before `today`."""
    return conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE deadline < ? AND status != 'completed'",
        (today,),
    ).fetchone()[0]