"""Business rules for DevTrack sessions. Sits between the CLI and the repositories.

Services decide WHAT is allowed; they never print and never write SQL.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from devtrack import repositories
from devtrack.timeutils import duration_seconds, to_iso


class ServiceError(Exception):
    """Raised when a request breaks a business rule; the message is safe to show."""


@dataclass(frozen=True)
class SessionRecord:
    """One session as the user should see it (seconds is time so far if still running)."""

    id: int
    project_name: str
    task_title: str | None
    started_at: str
    ended_at: str | None
    seconds: int
    running: bool


def start_session(
    conn: sqlite3.Connection, project_id: int, task_id: int | None, now: datetime
) -> int:
    """Start a session at `now` and return its id, or raise ServiceError."""
    active = repositories.get_active_session(conn)
    if active is not None:
        raise ServiceError(
            f"A session is already running on '{active['project_name']}'. Stop it first."
        )
    if repositories.get_project(conn, project_id) is None:
        raise ServiceError(f"No project with id {project_id}.")
    if task_id is not None:
        task = repositories.get_task(conn, task_id)
        if task is None:
            raise ServiceError(f"No task with id {task_id}.")
        if task["project_id"] != project_id:
            raise ServiceError(f"Task {task_id} does not belong to project {project_id}.")
    try:
        return repositories.start_session(conn, project_id, task_id, to_iso(now))
    except sqlite3.IntegrityError:
        # The checks above passed, so the only thing left is the database lock:
        # another terminal started a session a moment before us.
        raise ServiceError("A session is already running. Stop it first.") from None


def stop_session(conn: sqlite3.Connection, now: datetime) -> SessionRecord:
    """Stop the running session at `now` and return what was recorded, or raise ServiceError."""
    active = repositories.get_active_session(conn)
    if active is None:
        raise ServiceError("No session is running.")
    ended_at = to_iso(now)
    try:
        seconds = duration_seconds(active["started_at"], ended_at)
    except ValueError:
        raise ServiceError(
            "The clock is earlier than the session's start time; cannot stop it yet."
        ) from None
    if not repositories.stop_session(conn, active["id"], ended_at):
        raise ServiceError("No session is running.")  # stopped elsewhere just now
    return SessionRecord(
        id=active["id"],
        project_name=active["project_name"],
        task_title=active["task_title"],
        started_at=active["started_at"],
        ended_at=ended_at,
        seconds=seconds,
        running=False,
    )


def current_session(conn: sqlite3.Connection, now: datetime) -> SessionRecord | None:
    """Return the running session with its elapsed time so far, or None."""
    active = repositories.get_active_session(conn)
    if active is None:
        return None
    return _to_record(active, to_iso(now))


def recent_sessions(
    conn: sqlite3.Connection, now: datetime, limit: int = 20
) -> list[SessionRecord]:
    """Return recent sessions (newest first); a running one shows its time so far."""
    now_text = to_iso(now)
    return [_to_record(row, now_text) for row in repositories.list_sessions(conn, limit)]


def _to_record(row: sqlite3.Row, now_text: str) -> SessionRecord:
    """Build a SessionRecord from a database row."""
    running = row["ended_at"] is None
    end = now_text if running else row["ended_at"]
    try:
        seconds = duration_seconds(row["started_at"], end)
    except ValueError:  # clock moved backwards while running
        seconds = 0
    return SessionRecord(
        id=row["id"],
        project_name=row["project_name"],
        task_title=row["task_title"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        seconds=seconds,
        running=running,
    )