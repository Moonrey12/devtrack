from datetime import date, datetime, timedelta, timezone

import pytest

from devtrack import repositories, reports
from devtrack.reports import CompletedTask, ProjectStats, ProjectTime

UTC = timezone.utc
UTC_PLUS_8 = timezone(timedelta(hours=8))
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def iso(day, hour=0, minute=0, month=11):
    return f"2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00+00:00"


def add_session(conn, project_id, started, ended):
    session_id = repositories.start_session(conn, project_id, None, started)
    if ended is not None:
        repositories.stop_session(conn, session_id, ended)
    return session_id


def complete_at(conn, task_id, completed_at):
    with conn:
        conn.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (completed_at, task_id),
        )


@pytest.fixture
def alpha(conn):
    return repositories.add_project(conn, "Alpha", None, None)


@pytest.fixture
def beta(conn):
    return repositories.add_project(conn, "Beta", None, None)


# ---------- daily ----------

def test_daily_report_for_an_empty_day(conn):
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert (r.total_seconds, r.session_count) == (0, 0)
    assert r.by_project == [] and r.completed_tasks == []


def test_daily_report_totals_one_session(conn, alpha):
    add_session(conn, alpha, iso(5, 9), iso(5, 10, 30))
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert (r.total_seconds, r.session_count) == (5400, 1)
    assert r.by_project == [ProjectTime("Alpha", 5400)]


def test_daily_report_groups_by_project_largest_first(conn, alpha, beta):
    add_session(conn, alpha, iso(5, 8), iso(5, 9))
    add_session(conn, beta, iso(5, 10), iso(5, 12))
    add_session(conn, alpha, iso(5, 13), iso(5, 13, 30))
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert r.by_project == [ProjectTime("Beta", 7200), ProjectTime("Alpha", 5400)]
    assert (r.total_seconds, r.session_count) == (12600, 3)


def test_daily_report_ties_are_sorted_by_name(conn, alpha, beta):
    add_session(conn, beta, iso(5, 8), iso(5, 9))
    add_session(conn, alpha, iso(5, 10), iso(5, 11))
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert [p.project_name for p in r.by_project] == ["Alpha", "Beta"]


def test_daily_report_splits_a_session_that_crosses_midnight(conn, alpha):
    add_session(conn, alpha, iso(4, 23, 30), iso(5, 0, 30))
    before = reports.daily_report(conn, date(2026, 11, 4), NOW, UTC)
    after = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert (before.total_seconds, before.session_count) == (1800, 1)
    assert (after.total_seconds, after.session_count) == (1800, 1)


def test_daily_report_ignores_sessions_on_other_days(conn, alpha):
    add_session(conn, alpha, iso(4, 9), iso(4, 10))
    add_session(conn, alpha, iso(6, 9), iso(6, 10))
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert (r.total_seconds, r.session_count) == (0, 0)


def test_daily_report_running_session_counts_up_to_now(conn, alpha):
    add_session(conn, alpha, iso(5, 9), None)
    now = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
    r = reports.daily_report(conn, date(2026, 11, 5), now, UTC)
    assert (r.total_seconds, r.session_count) == (3600, 1)


def test_daily_report_does_not_count_a_running_session_on_a_future_day(conn, alpha):
    add_session(conn, alpha, iso(5, 9), None)
    now = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
    r = reports.daily_report(conn, date(2026, 11, 6), now, UTC)
    assert (r.total_seconds, r.session_count) == (0, 0)


def test_daily_report_does_not_count_zero_length_sessions(conn, alpha):
    add_session(conn, alpha, iso(5, 9), iso(5, 9))
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert (r.total_seconds, r.session_count) == (0, 0)


def test_daily_report_lists_only_tasks_completed_that_day(conn, alpha):
    ids = {n: repositories.add_task(conn, alpha, n) for n in ("early", "today", "next")}
    complete_at(conn, ids["early"], "2026-11-04 23:59:59")
    complete_at(conn, ids["today"], "2026-11-05 03:00:00")
    complete_at(conn, ids["next"], "2026-11-06 00:00:00")
    r = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC)
    assert r.completed_tasks == [CompletedTask("today", "Alpha")]


def test_daily_report_uses_the_local_day_not_the_utc_day(conn, alpha):
    add_session(conn, alpha, iso(5, 17), iso(5, 18))  # 01:00-02:00 on Nov 6 at UTC+8
    task = repositories.add_task(conn, alpha, "late night")
    complete_at(conn, task, "2026-11-05 17:00:00")
    nov5 = reports.daily_report(conn, date(2026, 11, 5), NOW, UTC_PLUS_8)
    nov6 = reports.daily_report(conn, date(2026, 11, 6), NOW, UTC_PLUS_8)
    assert nov5.total_seconds == 0 and nov5.completed_tasks == []
    assert nov6.total_seconds == 3600
    assert nov6.completed_tasks == [CompletedTask("late night", "Alpha")]


# ---------- weekly ----------

def test_weekly_report_has_seven_days_in_order(conn):
    r = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC)
    assert [d.day for d in r.days] == [date(2026, 11, n) for n in range(2, 9)]
    assert (r.first_day, r.last_day) == (date(2026, 11, 2), date(2026, 11, 8))


def test_weekly_report_total_equals_the_sum_of_its_days(conn, alpha, beta):
    add_session(conn, alpha, iso(2, 9), iso(2, 10))
    add_session(conn, beta, iso(4, 9), iso(4, 11))
    add_session(conn, alpha, iso(8, 20), iso(8, 21, 30))
    r = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC)
    assert r.total_seconds == sum(d.total_seconds for d in r.days) == 3600 + 7200 + 5400
    assert r.by_project == [ProjectTime("Alpha", 9000), ProjectTime("Beta", 7200)]
    assert r.session_count == 3


def test_weekly_report_counts_a_midnight_session_once(conn, alpha):
    add_session(conn, alpha, iso(3, 23, 30), iso(4, 0, 30))
    r = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC)
    assert r.session_count == 1
    assert sum(d.session_count for d in r.days) == 2
    assert r.total_seconds == 3600


def test_weekly_report_excludes_sessions_outside_the_week(conn, alpha):
    add_session(conn, alpha, iso(1, 9), iso(1, 10))
    add_session(conn, alpha, iso(9, 9), iso(9, 10))
    r = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC)
    assert (r.total_seconds, r.session_count) == (0, 0)


def test_weekly_report_can_start_on_sunday(conn, alpha):
    add_session(conn, alpha, iso(1, 9), iso(1, 10))  # a Sunday
    monday_weeks = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC, first_weekday=0)
    sunday_weeks = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC, first_weekday=6)
    assert monday_weeks.total_seconds == 0
    assert sunday_weeks.total_seconds == 3600
    assert sunday_weeks.first_day == date(2026, 11, 1)


def test_weekly_report_crosses_a_month_boundary(conn):
    r = reports.weekly_report(conn, date(2026, 12, 2), NOW, UTC)
    assert (r.first_day, r.last_day) == (date(2026, 11, 30), date(2026, 12, 6))


def test_weekly_report_lists_tasks_completed_during_the_week(conn, alpha):
    ids = {n: repositories.add_task(conn, alpha, n) for n in ("before", "during", "after")}
    complete_at(conn, ids["before"], "2026-11-01 23:00:00")
    complete_at(conn, ids["during"], "2026-11-05 10:00:00")
    complete_at(conn, ids["after"], "2026-11-09 00:00:00")
    r = reports.weekly_report(conn, date(2026, 11, 4), NOW, UTC)
    assert r.completed_tasks == [CompletedTask("during", "Alpha")]


# ---------- stats ----------

def test_stats_for_an_empty_database(conn):
    s = reports.stats_report(conn, NOW, UTC)
    assert s.today == date(2026, 11, 10)
    assert s.total_tasks == 0 and s.completion_percent is None
    assert s.by_status == {"todo": 0, "in_progress": 0, "completed": 0}
    assert (s.completed_last_7_days, s.overdue, s.by_project) == (0, 0, [])


def test_stats_counts_statuses_and_completion_percent(conn, alpha):
    ids = [repositories.add_task(conn, alpha, n) for n in ("a", "b", "c", "d")]
    repositories.update_task_status(conn, ids[0], "completed")
    repositories.update_task_status(conn, ids[1], "in_progress")
    s = reports.stats_report(conn, NOW, UTC)
    assert s.total_tasks == 4
    assert s.by_status == {"todo": 2, "in_progress": 1, "completed": 1}
    assert s.completion_percent == 25.0


def test_stats_completion_percent_is_rounded_to_one_decimal(conn, alpha):
    ids = [repositories.add_task(conn, alpha, n) for n in ("a", "b", "c")]
    repositories.update_task_status(conn, ids[0], "completed")
    assert reports.stats_report(conn, NOW, UTC).completion_percent == 33.3


def test_stats_last_7_days_means_today_and_the_six_days_before(conn, alpha):
    ids = {n: repositories.add_task(conn, alpha, n) for n in ("too old", "edge", "today")}
    complete_at(conn, ids["too old"], "2026-11-03 23:59:59")
    complete_at(conn, ids["edge"], "2026-11-04 00:00:00")
    complete_at(conn, ids["today"], "2026-11-10 11:00:00")
    assert reports.stats_report(conn, NOW, UTC).completed_last_7_days == 2


def test_stats_overdue_uses_the_local_date(conn, alpha):
    now = datetime(2026, 11, 5, 17, 0, tzinfo=UTC)  # already Nov 6 at UTC+8
    repositories.add_task(conn, alpha, "due Nov 5", deadline="2026-11-05")
    repositories.add_task(conn, alpha, "due Nov 6", deadline="2026-11-06")
    local = reports.stats_report(conn, now, UTC_PLUS_8)
    utc = reports.stats_report(conn, now, UTC)
    assert local.today == date(2026, 11, 6) and local.overdue == 1
    assert utc.today == date(2026, 11, 5) and utc.overdue == 0


def test_stats_by_project_includes_projects_without_tasks(conn, alpha, beta):
    t = repositories.add_task(conn, alpha, "x")
    repositories.add_task(conn, alpha, "y")
    repositories.update_task_status(conn, t, "completed")
    s = reports.stats_report(conn, NOW, UTC)
    assert s.by_project == [ProjectStats("Alpha", 2, 1), ProjectStats("Beta", 0, 0)]