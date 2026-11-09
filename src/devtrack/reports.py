"""Report builders: turn sessions and tasks into plain data. Never prints, never writes SQL."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from devtrack import repositories
from devtrack.timeutils import (
    day_window,
    session_seconds_in_window,
    to_iso,
    to_sqlite_text,
    week_days,
    week_window,
)


@dataclass(frozen=True)
class ProjectTime:
    """Coding time spent on one project."""

    project_name: str
    seconds: int


@dataclass(frozen=True)
class CompletedTask:
    """A task that was completed inside a report's window."""

    title: str
    project_name: str


@dataclass(frozen=True)
class DailyReport:
    """Coding time and completed tasks for one local day."""

    day: date
    total_seconds: int
    session_count: int
    by_project: list[ProjectTime]
    completed_tasks: list[CompletedTask]


@dataclass(frozen=True)
class WeeklyReport:
    """Coding time and completed tasks for one local week, plus each day."""

    first_day: date
    last_day: date
    total_seconds: int
    session_count: int
    by_project: list[ProjectTime]
    completed_tasks: list[CompletedTask]
    days: list[DailyReport]


@dataclass(frozen=True)
class ProjectStats:
    """Task totals for one project."""

    project_name: str
    total: int
    completed: int


@dataclass(frozen=True)
class StatsReport:
    """Task statistics as of one local day."""

    today: date
    total_tasks: int
    by_status: dict[str, int]
    completion_percent: float | None
    completed_last_7_days: int
    overdue: int
    by_project: list[ProjectStats]


def _time_in_window(
    conn: sqlite3.Connection, window_start: datetime, window_end: datetime, now: datetime
) -> tuple[int, int, list[ProjectTime]]:
    """Return (total seconds, session count, per-project time) for sessions inside a window."""
    rows = repositories.sessions_overlapping(conn, to_iso(window_start), to_iso(window_end))
    per_project: dict[str, int] = {}
    count = 0
    for row in rows:
        seconds = session_seconds_in_window(
            row["started_at"], row["ended_at"], now, window_start, window_end
        )
        if seconds <= 0:
            continue  # only touches the window, or has not really started yet
        count += 1
        name = row["project_name"]
        per_project[name] = per_project.get(name, 0) + seconds
    ranked = sorted(per_project.items(), key=lambda item: (-item[1], item[0]))
    return sum(per_project.values()), count, [ProjectTime(n, s) for n, s in ranked]


def _completed_in_window(
    conn: sqlite3.Connection, window_start: datetime, window_end: datetime
) -> list[CompletedTask]:
    """Return tasks completed inside a window (completed_at uses SQLite's own time format)."""
    rows = repositories.tasks_completed_between(
        conn, to_sqlite_text(window_start), to_sqlite_text(window_end)
    )
    return [CompletedTask(row["title"], row["project_name"]) for row in rows]


def daily_report(
    conn: sqlite3.Connection, day: date, now: datetime, tz: tzinfo | None = None
) -> DailyReport:
    """Build the report for one local day."""
    start, end = day_window(day, tz)
    total, count, by_project = _time_in_window(conn, start, end, now)
    return DailyReport(day, total, count, by_project, _completed_in_window(conn, start, end))


def weekly_report(
    conn: sqlite3.Connection,
    day: date,
    now: datetime,
    tz: tzinfo | None = None,
    first_weekday: int = 0,
) -> WeeklyReport:
    """Build the report for the local week containing `day`."""
    days = week_days(day, first_weekday)
    start, end = week_window(day, tz, first_weekday)
    total, count, by_project = _time_in_window(conn, start, end, now)
    return WeeklyReport(
        first_day=days[0],
        last_day=days[-1],
        total_seconds=total,
        session_count=count,
        by_project=by_project,
        completed_tasks=_completed_in_window(conn, start, end),
        days=[daily_report(conn, d, now, tz) for d in days],
    )


def stats_report(
    conn: sqlite3.Connection, now: datetime, tz: tzinfo | None = None
) -> StatsReport:
    """Build task statistics as of the local day containing `now`."""
    today = now.astimezone(tz).date()
    by_status = repositories.count_tasks_by_status(conn)
    total = sum(by_status.values())
    percent = round(100 * by_status["completed"] / total, 1) if total else None
    # "Last 7 days" = today plus the six previous local days.
    window_start = day_window(today - timedelta(days=6), tz)[0]
    window_end = day_window(today, tz)[1]
    recent = _completed_in_window(conn, window_start, window_end)
    return StatsReport(
        today=today,
        total_tasks=total,
        by_status=by_status,
        completion_percent=percent,
        completed_last_7_days=len(recent),
        overdue=repositories.count_overdue_tasks(conn, today.isoformat()),
        by_project=[
            ProjectStats(row["name"], row["total"], row["completed"])
            for row in repositories.task_counts_by_project(conn)
        ],
    )