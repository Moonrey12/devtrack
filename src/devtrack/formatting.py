"""Plain-text renderers for reports. They turn report data into strings and never print."""

from devtrack.reports import CompletedTask, DailyReport, ProjectTime, StatsReport, WeeklyReport
from devtrack.timeutils import format_duration

WEEKDAY_NAMES = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
BAR_WIDTH = 20
NAME_WIDTH = 24


def _plural(count: int, word: str) -> str:
    """Return '1 session' or '3 sessions'."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _coding_time_line(total_seconds: int, session_count: int) -> str:
    """Return the 'Coding time: ...' summary line."""
    if total_seconds == 0 and session_count == 0:
        return "Coding time: none"
    return f"Coding time: {format_duration(total_seconds)} in {_plural(session_count, 'session')}"


def _project_lines(by_project: list[ProjectTime]) -> list[str]:
    """Return one aligned line per project."""
    if not by_project:
        return []
    width = min(NAME_WIDTH, max(len(p.project_name) for p in by_project))
    return [
        f"  {p.project_name[:NAME_WIDTH]:<{width}}  {format_duration(p.seconds)}"
        for p in by_project
    ]


def _completed_lines(tasks: list[CompletedTask], label: str) -> list[str]:
    """Return the completed-tasks summary and one line per task."""
    if not tasks:
        return [f"{label}: none"]
    return [f"{label}: {len(tasks)}"] + [f"  - {t.title} ({t.project_name})" for t in tasks]


def _bar(seconds: int, biggest: int) -> str:
    """Return a text bar scaled to the busiest day (at least one '#' if there was any time)."""
    if biggest <= 0 or seconds <= 0:
        return ""
    return "#" * max(1, round(BAR_WIDTH * seconds / biggest))


def render_daily(report: DailyReport) -> str:
    """Render a daily report as text."""
    lines = [
        f"Daily report: {WEEKDAY_NAMES[report.day.weekday()]} {report.day.isoformat()}",
        _coding_time_line(report.total_seconds, report.session_count),
    ]
    lines += _project_lines(report.by_project)
    lines += _completed_lines(report.completed_tasks, "Tasks completed")
    return "\n".join(lines)


def render_weekly(report: WeeklyReport) -> str:
    """Render a weekly report as text, with a simple bar per day."""
    lines = [
        f"Weekly report: {report.first_day.isoformat()} to {report.last_day.isoformat()}",
        _coding_time_line(report.total_seconds, report.session_count),
    ]
    lines += _project_lines(report.by_project)
    biggest = max((d.total_seconds for d in report.days), default=0)
    lines.append("By day:")
    for d in report.days:
        label = f"{WEEKDAY_NAMES[d.day.weekday()][:3]} {d.day.month:02d}-{d.day.day:02d}"
        duration = format_duration(d.total_seconds) if d.total_seconds else "-"
        lines.append(f"  {label}  {_bar(d.total_seconds, biggest):<{BAR_WIDTH}}  {duration}")
    lines += _completed_lines(report.completed_tasks, "Tasks completed this week")
    return "\n".join(lines)


def render_stats(report: StatsReport) -> str:
    """Render task statistics as text."""
    lines = [
        f"Task statistics (as of {report.today.isoformat()})",
        f"Total tasks: {report.total_tasks}",
    ]
    if report.total_tasks == 0:
        lines.append("No tasks yet. Add one with: devtrack task add PROJECT_ID TITLE")
    else:
        for status in ("todo", "in_progress", "completed"):
            line = f"  {status:<12} {report.by_status[status]}"
            if status == "completed" and report.completion_percent is not None:
                line += f"   ({report.completion_percent:.1f}% complete)"
            lines.append(line)
    lines.append(f"Completed in the last 7 days: {report.completed_last_7_days}")
    lines.append(f"Overdue: {report.overdue}")
    if report.by_project:
        width = min(NAME_WIDTH, max(len(p.project_name) for p in report.by_project))
        lines.append("By project:")
        lines += [
            f"  {p.project_name[:NAME_WIDTH]:<{width}}  {p.completed}/{p.total} completed"
            for p in report.by_project
        ]
    return "\n".join(lines)