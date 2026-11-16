from datetime import date

from devtrack.formatting import BAR_WIDTH, render_daily, render_stats, render_weekly
from devtrack.reports import (
    CompletedTask,
    DailyReport,
    ProjectStats,
    ProjectTime,
    StatsReport,
    WeeklyReport,
)


def daily(day, seconds=0, count=0, by_project=(), tasks=()):
    return DailyReport(day, seconds, count, list(by_project), list(tasks))


def test_render_daily_with_data():
    report = daily(
        date(2026, 11, 5), 11520, 4,
        [ProjectTime("Portfolio", 9000), ProjectTime("Blog", 2520)],
        [CompletedTask("Fix login bug", "Portfolio")],
    )
    lines = render_daily(report).splitlines()
    assert lines[0] == "Daily report: Thursday 2026-11-05"
    assert lines[1] == "Coding time: 3h 12m 0s in 4 sessions"
    assert lines[2] == "  Portfolio  2h 30m 0s"
    assert lines[3] == "  Blog       42m 0s"
    assert lines[4] == "Tasks completed: 1"
    assert lines[5] == "  - Fix login bug (Portfolio)"


def test_render_daily_for_an_empty_day():
    lines = render_daily(daily(date(2026, 11, 5))).splitlines()
    assert lines == [
        "Daily report: Thursday 2026-11-05",
        "Coding time: none",
        "Tasks completed: none",
    ]


def test_render_daily_uses_singular_for_one_session():
    text = render_daily(daily(date(2026, 11, 5), 600, 1, [ProjectTime("P", 600)]))
    assert "in 1 session\n" in text + "\n"
    assert "1 sessions" not in text


def test_render_daily_names_the_right_weekday():
    assert "Monday 2026-11-02" in render_daily(daily(date(2026, 11, 2)))
    assert "Sunday 2026-11-08" in render_daily(daily(date(2026, 11, 8)))


def test_render_daily_shortens_very_long_project_names():
    long_name = "x" * 60
    text = render_daily(daily(date(2026, 11, 5), 60, 1, [ProjectTime(long_name, 60)]))
    assert ("x" * 24) in text and ("x" * 25) not in text


def weekly(seconds_per_day, **kwargs):
    days = [daily(date(2026, 11, 2 + i), s, 1 if s else 0) for i, s in enumerate(seconds_per_day)]
    return WeeklyReport(
        first_day=date(2026, 11, 2),
        last_day=date(2026, 11, 8),
        total_seconds=sum(seconds_per_day),
        session_count=sum(1 for s in seconds_per_day if s),
        by_project=kwargs.get("by_project", []),
        completed_tasks=kwargs.get("tasks", []),
        days=days,
    )


def day_line(text, label):
    return [ln for ln in text.splitlines() if ln.strip().startswith(label)][0]


def test_render_weekly_header_and_totals():
    text = render_weekly(weekly([3600, 0, 0, 0, 0, 0, 0], by_project=[ProjectTime("P", 3600)]))
    lines = text.splitlines()
    assert lines[0] == "Weekly report: 2026-11-02 to 2026-11-08"
    assert lines[1] == "Coding time: 1h 0m 0s in 1 session"
    assert "By day:" in lines


def test_render_weekly_scales_bars_to_the_busiest_day():
    text = render_weekly(weekly([7200, 3600, 0, 0, 0, 0, 0]))
    assert day_line(text, "Mon 11-02").count("#") == BAR_WIDTH
    assert day_line(text, "Tue 11-03").count("#") == BAR_WIDTH // 2


def test_render_weekly_shows_a_dash_and_no_bar_for_empty_days():
    text = render_weekly(weekly([3600, 0, 0, 0, 0, 0, 0]))
    wed = day_line(text, "Wed 11-04")
    assert "#" not in wed and wed.rstrip().endswith("-")


def test_render_weekly_gives_tiny_days_at_least_one_mark():
    text = render_weekly(weekly([36000, 60, 0, 0, 0, 0, 0]))
    assert day_line(text, "Tue 11-03").count("#") == 1


def test_render_weekly_lists_completed_tasks():
    text = render_weekly(weekly([0] * 7, tasks=[CompletedTask("Ship it", "P")]))
    assert "Tasks completed this week: 1" in text and "  - Ship it (P)" in text


def test_render_weekly_with_no_activity_has_no_bars():
    text = render_weekly(weekly([0] * 7))
    assert "#" not in text
    assert "Coding time: none" in text and "Tasks completed this week: none" in text


def stats(**kwargs):
    base = dict(
        today=date(2026, 11, 5), total_tasks=0,
        by_status={"todo": 0, "in_progress": 0, "completed": 0},
        completion_percent=None, completed_last_7_days=0, overdue=0, by_project=[],
    )
    base.update(kwargs)
    return StatsReport(**base)


def test_render_stats_for_an_empty_database_gives_a_hint():
    text = render_stats(stats())
    assert "Total tasks: 0" in text
    assert "No tasks yet" in text
    assert "% complete" not in text


def test_render_stats_with_data():
    text = render_stats(stats(
        total_tasks=12,
        by_status={"todo": 5, "in_progress": 2, "completed": 5},
        completion_percent=41.7, completed_last_7_days=3, overdue=1,
        by_project=[ProjectStats("Portfolio", 5, 3), ProjectStats("Blog", 7, 2)],
    ))
    assert "Task statistics (as of 2026-11-05)" in text
    assert "  completed    5   (41.7% complete)" in text
    assert "Completed in the last 7 days: 3" in text
    assert "Overdue: 1" in text
    assert "  Portfolio  3/5 completed" in text
    assert "  Blog       2/7 completed" in text