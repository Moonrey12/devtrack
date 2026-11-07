import sqlite3

import pytest

from devtrack import repositories


def test_add_project_and_get_it(conn):
    project_id = repositories.add_project(conn, "Portfolio", "My site", "Python")
    project = repositories.get_project(conn, project_id)
    assert project["name"] == "Portfolio"
    assert project["tech_stack"] == "Python"


def test_duplicate_project_name_raises(conn):
    repositories.add_project(conn, "Portfolio", None, None)
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_project(conn, "Portfolio", None, None)


def test_get_project_missing_returns_none(conn):
    assert repositories.get_project(conn, 99) is None


def test_list_projects_in_id_order(conn):
    first = repositories.add_project(conn, "B", None, None)
    second = repositories.add_project(conn, "A", None, None)
    ids = [p["id"] for p in repositories.list_projects(conn)]
    assert ids == [first, second]


def test_add_task_defaults_to_todo(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "Write tests")
    assert repositories.get_task(conn, task_id)["status"] == "todo"


def test_add_task_for_missing_project_raises(conn):
    with pytest.raises(sqlite3.IntegrityError):
        repositories.add_task(conn, 999, "Orphan")


def test_list_tasks_filters_by_status(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    first = repositories.add_task(conn, project_id, "One")
    repositories.add_task(conn, project_id, "Two")
    repositories.update_task_status(conn, first, "in_progress")
    assert len(repositories.list_tasks(conn, project_id)) == 2
    in_progress = repositories.list_tasks(conn, project_id, "in_progress")
    assert [t["title"] for t in in_progress] == ["One"]
    assert repositories.list_tasks(conn, project_id, "completed") == []


def test_update_task_status_returns_true_then_false_for_missing(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "One")
    assert repositories.update_task_status(conn, task_id, "in_progress") is True
    assert repositories.update_task_status(conn, 999, "todo") is False


def test_completed_at_is_set_and_cleared(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "One")
    assert repositories.get_task(conn, task_id)["completed_at"] is None
    repositories.update_task_status(conn, task_id, "completed")
    assert repositories.get_task(conn, task_id)["completed_at"] is not None
    repositories.update_task_status(conn, task_id, "todo")
    assert repositories.get_task(conn, task_id)["completed_at"] is None


def test_delete_task_true_then_false(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "One")
    assert repositories.delete_task(conn, task_id) is True
    assert repositories.delete_task(conn, task_id) is False


def test_deleting_project_cascades_to_tasks(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    repositories.add_task(conn, project_id, "One")
    with conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    assert repositories.list_tasks(conn, project_id) == []

def test_add_task_with_priority_and_deadline(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "One", priority=3, deadline="2026-12-31")
    task = repositories.get_task(conn, task_id)
    assert task["priority"] == 3
    assert task["deadline"] == "2026-12-31"


def test_set_task_priority_deadline_updates_and_clears(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "One")
    assert repositories.set_task_priority_deadline(conn, task_id, 2, "2026-11-30") is True
    task = repositories.get_task(conn, task_id)
    assert (task["priority"], task["deadline"]) == (2, "2026-11-30")
    repositories.set_task_priority_deadline(conn, task_id, None, None)
    task = repositories.get_task(conn, task_id)
    assert (task["priority"], task["deadline"]) == (None, None)


def test_set_task_priority_deadline_missing_task_returns_false(conn):
    assert repositories.set_task_priority_deadline(conn, 999, 1, None) is False


def _titles(rows):
    return [row["title"] for row in rows]


def _seed_search_data(conn):
    p1 = repositories.add_project(conn, "Alpha", None, None)
    p2 = repositories.add_project(conn, "Beta", None, None)
    repositories.add_task(conn, p1, "Write tests")
    repositories.add_task(conn, p2, "TEST plan")
    repositories.add_task(conn, p1, "Reach 100% coverage")
    repositories.add_task(conn, p1, "Handle 1000 users")
    repositories.add_task(conn, p2, "rename a_b file")
    repositories.add_task(conn, p2, "rename axb file")


def test_search_without_text_returns_all_tasks_across_projects(conn):
    _seed_search_data(conn)
    assert len(repositories.search_tasks(conn)) == 6


def test_search_matches_title_text_ignoring_case(conn):
    _seed_search_data(conn)
    found = repositories.search_tasks(conn, "test")
    assert _titles(found) == ["Write tests", "TEST plan"]


def test_search_results_include_project_name(conn):
    _seed_search_data(conn)
    found = repositories.search_tasks(conn, "plan")
    assert found[0]["project_name"] == "Beta"


def test_search_no_match_returns_empty_list(conn):
    _seed_search_data(conn)
    assert repositories.search_tasks(conn, "zzz") == []


def test_search_treats_percent_literally(conn):
    _seed_search_data(conn)
    assert _titles(repositories.search_tasks(conn, "100%")) == ["Reach 100% coverage"]


def test_search_treats_underscore_literally(conn):
    _seed_search_data(conn)
    assert _titles(repositories.search_tasks(conn, "a_b")) == ["rename a_b file"]

def _add_task(conn, project_id, title, priority=None, deadline=None, status="todo"):
    task_id = repositories.add_task(conn, project_id, title, priority, deadline)
    if status != "todo":
        repositories.update_task_status(conn, task_id, status)
    return task_id


def _seed_filter_data(conn):
    a = repositories.add_project(conn, "Alpha", None, None)
    b = repositories.add_project(conn, "Beta", None, None)
    _add_task(conn, a, "Fix bug", 3, "2026-11-01")
    _add_task(conn, a, "Write docs", 1, "2026-12-15")
    _add_task(conn, a, "Old report", 2, "2026-10-01", "completed")
    _add_task(conn, a, "No date")
    _add_task(conn, b, "Deploy app", 3, "2026-11-20", "in_progress")
    _add_task(conn, b, "Refactor", 1, "2026-09-15", "in_progress")
    return a, b


def test_search_filters_by_project(conn):
    a, b = _seed_filter_data(conn)
    assert _titles(repositories.search_tasks(conn, project_id=b)) == ["Deploy app", "Refactor"]


def test_search_filters_by_status(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, status="in_progress")
    assert _titles(found) == ["Deploy app", "Refactor"]


def test_search_filters_by_priority(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, priority=3)
    assert _titles(found) == ["Fix bug", "Deploy app"]


def test_search_due_by_is_inclusive_and_skips_tasks_without_deadline(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, due_by="2026-11-20")
    assert _titles(found) == ["Fix bug", "Old report", "Deploy app", "Refactor"]


def test_search_overdue_skips_completed_future_and_undated(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, overdue=True, today="2026-11-10")
    assert _titles(found) == ["Fix bug", "Refactor"]


def test_search_overdue_does_not_include_a_task_due_today(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, overdue=True, today="2026-11-01")
    assert _titles(found) == ["Refactor"]


def test_search_overdue_requires_today(conn):
    with pytest.raises(ValueError):
        repositories.search_tasks(conn, overdue=True)


def test_search_filters_combine_with_and(conn):
    a, b = _seed_filter_data(conn)
    found = repositories.search_tasks(conn, project_id=b, priority=3, status="in_progress")
    assert _titles(found) == ["Deploy app"]


def test_search_text_combines_with_filters(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, "re", priority=1)
    assert _titles(found) == ["Refactor"]


def test_search_default_sort_is_by_id(conn):
    _seed_filter_data(conn)
    assert _titles(repositories.search_tasks(conn)) == [
        "Fix bug", "Write docs", "Old report", "No date", "Deploy app", "Refactor",
    ]


def test_search_sort_by_deadline_earliest_first_and_undated_last(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, sort="deadline")
    assert _titles(found) == [
        "Refactor", "Old report", "Fix bug", "Deploy app", "Write docs", "No date",
    ]


def test_search_sort_by_priority_high_first_and_unprioritized_last(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, sort="priority")
    assert _titles(found) == [
        "Fix bug", "Deploy app", "Old report", "Write docs", "Refactor", "No date",
    ]


def test_search_sort_by_title_ignores_case(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    for title in ("apple", "Banana", "cherry"):
        repositories.add_task(conn, project_id, title)
    found = repositories.search_tasks(conn, sort="title")
    assert _titles(found) == ["apple", "Banana", "cherry"]


def test_search_sort_works_together_with_filters(conn):
    _seed_filter_data(conn)
    found = repositories.search_tasks(conn, priority=1, sort="deadline")
    assert _titles(found) == ["Refactor", "Write docs"]


@pytest.mark.parametrize("bad_sort", ["nope", "", "id; DROP TABLE tasks", "tasks.id DESC"])
def test_search_rejects_unknown_sort(conn, bad_sort):
    with pytest.raises(ValueError):
        repositories.search_tasks(conn, sort=bad_sort)

T0 = "2026-11-02T09:00:00+00:00"
T1 = "2026-11-02T10:30:00+00:00"
T2 = "2026-11-02T11:00:00+00:00"


def test_start_session_then_it_is_active(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    session_id = repositories.start_session(conn, project_id, None, T0)
    active = repositories.get_active_session(conn)
    assert active["id"] == session_id
    assert active["project_name"] == "P"
    assert active["started_at"] == T0
    assert active["ended_at"] is None
    assert active["task_title"] is None


def test_no_active_session_returns_none(conn):
    assert repositories.get_active_session(conn) is None


def test_stop_session_records_end_time_and_clears_active(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    session_id = repositories.start_session(conn, project_id, None, T0)
    assert repositories.stop_session(conn, session_id, T1) is True
    assert repositories.get_active_session(conn) is None
    stored = repositories.list_sessions(conn)[0]
    assert (stored["started_at"], stored["ended_at"]) == (T0, T1)


def test_database_allows_only_one_active_session(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    repositories.start_session(conn, project_id, None, T0)
    with pytest.raises(sqlite3.IntegrityError):
        repositories.start_session(conn, project_id, None, T1)


def test_new_session_allowed_after_previous_one_stopped(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    first = repositories.start_session(conn, project_id, None, T0)
    repositories.stop_session(conn, first, T1)
    second = repositories.start_session(conn, project_id, None, T1)
    assert second != first


def test_stop_session_twice_or_missing_returns_false(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    session_id = repositories.start_session(conn, project_id, None, T0)
    assert repositories.stop_session(conn, session_id, T1) is True
    assert repositories.stop_session(conn, session_id, T2) is False
    assert repositories.stop_session(conn, 999, T2) is False
    # The original end time was not overwritten by the second stop.
    assert repositories.list_sessions(conn)[0]["ended_at"] == T1


def test_session_cannot_end_before_it_started(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    session_id = repositories.start_session(conn, project_id, None, T1)
    with pytest.raises(sqlite3.IntegrityError):
        repositories.stop_session(conn, session_id, T0)


def test_session_for_missing_project_raises(conn):
    with pytest.raises(sqlite3.IntegrityError):
        repositories.start_session(conn, 999, None, T0)


def test_deleting_a_task_keeps_its_session_but_forgets_the_task(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "Temp task")
    session_id = repositories.start_session(conn, project_id, task_id, T0)
    repositories.stop_session(conn, session_id, T1)
    assert repositories.delete_task(conn, task_id) is True
    kept = repositories.list_sessions(conn)
    assert len(kept) == 1
    assert kept[0]["task_id"] is None
    assert kept[0]["task_title"] is None


def test_deleting_a_project_deletes_its_sessions(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    session_id = repositories.start_session(conn, project_id, None, T0)
    repositories.stop_session(conn, session_id, T1)
    with conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    assert repositories.list_sessions(conn) == []


def test_list_sessions_newest_first_with_task_title(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, project_id, "Write code")
    first = repositories.start_session(conn, project_id, None, T0)
    repositories.stop_session(conn, first, T1)
    second = repositories.start_session(conn, project_id, task_id, T1)
    repositories.stop_session(conn, second, T2)
    found = repositories.list_sessions(conn)
    assert [row["id"] for row in found] == [second, first]
    assert found[0]["task_title"] == "Write code"


def test_list_sessions_respects_limit(conn):
    project_id = repositories.add_project(conn, "P", None, None)
    for i in range(3):
        sid = repositories.start_session(conn, project_id, None, f"2026-11-0{i+1}T09:00:00+00:00")
        repositories.stop_session(conn, sid, f"2026-11-0{i+1}T10:00:00+00:00")
    assert len(repositories.list_sessions(conn, limit=2)) == 2

W_START = "2026-11-05T00:00:00+00:00"
W_END = "2026-11-06T00:00:00+00:00"


def _session(conn, project_id, started, ended):
    session_id = repositories.start_session(conn, project_id, None, started)
    if ended is not None:
        repositories.stop_session(conn, session_id, ended)
    return session_id


def test_sessions_overlapping_picks_every_way_of_touching_the_window(conn):
    p = repositories.add_project(conn, "P", None, None)
    inside = _session(conn, p, "2026-11-05T09:00:00+00:00", "2026-11-05T10:00:00+00:00")
    from_before = _session(conn, p, "2026-11-04T23:30:00+00:00", "2026-11-05T00:30:00+00:00")
    into_after = _session(conn, p, "2026-11-05T23:30:00+00:00", "2026-11-06T00:30:00+00:00")
    spanning = _session(conn, p, "2026-11-04T12:00:00+00:00", "2026-11-07T12:00:00+00:00")
    found = repositories.sessions_overlapping(conn, W_START, W_END)
    assert sorted(r["id"] for r in found) == sorted([inside, from_before, into_after, spanning])


def test_sessions_overlapping_skips_sessions_outside_or_only_touching(conn):
    p = repositories.add_project(conn, "P", None, None)
    _session(conn, p, "2026-11-04T20:00:00+00:00", "2026-11-04T22:00:00+00:00")  # before
    _session(conn, p, "2026-11-06T01:00:00+00:00", "2026-11-06T02:00:00+00:00")  # after
    _session(conn, p, "2026-11-04T23:00:00+00:00", "2026-11-05T00:00:00+00:00")  # ends at start
    _session(conn, p, "2026-11-06T00:00:00+00:00", "2026-11-06T01:00:00+00:00")  # starts at end
    assert repositories.sessions_overlapping(conn, W_START, W_END) == []


def test_sessions_overlapping_includes_running_sessions_that_started_before_the_end(conn):
    p = repositories.add_project(conn, "P", None, None)
    running = _session(conn, p, "2026-11-05T22:00:00+00:00", None)
    found = repositories.sessions_overlapping(conn, W_START, W_END)
    assert [r["id"] for r in found] == [running]
    assert found[0]["ended_at"] is None


def test_sessions_overlapping_excludes_a_running_session_that_starts_after_the_window(conn):
    p = repositories.add_project(conn, "P", None, None)
    _session(conn, p, "2026-11-06T00:00:00+00:00", None)
    assert repositories.sessions_overlapping(conn, W_START, W_END) == []


def test_sessions_overlapping_has_project_name_and_orders_by_start(conn):
    a = repositories.add_project(conn, "Alpha", None, None)
    b = repositories.add_project(conn, "Beta", None, None)
    later = _session(conn, b, "2026-11-05T15:00:00+00:00", "2026-11-05T16:00:00+00:00")
    earlier = _session(conn, a, "2026-11-05T09:00:00+00:00", "2026-11-05T10:00:00+00:00")
    found = repositories.sessions_overlapping(conn, W_START, W_END)
    assert [r["id"] for r in found] == [earlier, later]
    assert [r["project_name"] for r in found] == ["Alpha", "Beta"]


def _complete_at(conn, task_id, completed_at):
    with conn:
        conn.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (completed_at, task_id),
        )


def test_tasks_completed_between_uses_a_half_open_window(conn):
    p = repositories.add_project(conn, "P", None, None)
    ids = {name: repositories.add_task(conn, p, name) for name in
           ("before", "at_start", "inside", "at_end", "after")}
    _complete_at(conn, ids["before"], "2026-11-04 23:59:59")
    _complete_at(conn, ids["at_start"], "2026-11-05 00:00:00")
    _complete_at(conn, ids["inside"], "2026-11-05 12:00:00")
    _complete_at(conn, ids["at_end"], "2026-11-06 00:00:00")
    _complete_at(conn, ids["after"], "2026-11-06 08:00:00")
    found = repositories.tasks_completed_between(conn, "2026-11-05 00:00:00", "2026-11-06 00:00:00")
    assert _titles(found) == ["at_start", "inside"]


def test_tasks_completed_between_ignores_tasks_that_are_not_completed(conn):
    p = repositories.add_project(conn, "P", None, None)
    done = repositories.add_task(conn, p, "done")
    repositories.add_task(conn, p, "still todo")
    reopened = repositories.add_task(conn, p, "reopened")
    _complete_at(conn, done, "2026-11-05 12:00:00")
    _complete_at(conn, reopened, "2026-11-05 13:00:00")
    repositories.update_task_status(conn, reopened, "todo")  # clears completed_at
    found = repositories.tasks_completed_between(conn, "2026-11-05 00:00:00", "2026-11-06 00:00:00")
    assert _titles(found) == ["done"]
    assert found[0]["project_name"] == "P"


def test_real_completion_timestamp_is_found_by_a_window_around_now(conn):
    from datetime import datetime, timedelta, timezone
    from devtrack.timeutils import to_sqlite_text

    p = repositories.add_project(conn, "P", None, None)
    task_id = repositories.add_task(conn, p, "just now")
    repositories.update_task_status(conn, task_id, "completed")  # SQLite stamps the time
    now = datetime.now(timezone.utc)
    found = repositories.tasks_completed_between(
        conn,
        to_sqlite_text(now - timedelta(minutes=5)),
        to_sqlite_text(now + timedelta(minutes=5)),
    )
    assert _titles(found) == ["just now"]


def test_count_tasks_by_status_defaults_to_zero(conn):
    assert repositories.count_tasks_by_status(conn) == {"todo": 0, "in_progress": 0, "completed": 0}


def test_count_tasks_by_status_counts_each_group(conn):
    p = repositories.add_project(conn, "P", None, None)
    a = repositories.add_task(conn, p, "a")
    b = repositories.add_task(conn, p, "b")
    repositories.add_task(conn, p, "c")
    repositories.update_task_status(conn, a, "completed")
    repositories.update_task_status(conn, b, "in_progress")
    assert repositories.count_tasks_by_status(conn) == {"todo": 1, "in_progress": 1, "completed": 1}


def test_task_counts_by_project_includes_projects_without_tasks_in_name_order(conn):
    zeta = repositories.add_project(conn, "zeta", None, None)
    alpha = repositories.add_project(conn, "Alpha", None, None)
    repositories.add_project(conn, "Empty", None, None)
    t1 = repositories.add_task(conn, alpha, "x")
    repositories.add_task(conn, alpha, "y")
    repositories.update_task_status(conn, t1, "completed")
    repositories.add_task(conn, zeta, "z")
    rows = repositories.task_counts_by_project(conn)
    assert [(r["name"], r["total"], r["completed"]) for r in rows] == [
        ("Alpha", 2, 1),
        ("Empty", 0, 0),
        ("zeta", 1, 0),
    ]


def test_count_overdue_tasks(conn):
    p = repositories.add_project(conn, "P", None, None)
    _add_task(conn, p, "late", deadline="2026-11-01")
    _add_task(conn, p, "due today", deadline="2026-11-05")
    _add_task(conn, p, "future", deadline="2026-12-01")
    _add_task(conn, p, "no deadline")
    _add_task(conn, p, "late but done", deadline="2026-10-01", status="completed")
    assert repositories.count_overdue_tasks(conn, "2026-11-05") == 1


def test_sessions_overlapping_orders_by_start_time_not_by_id(conn):
    p = repositories.add_project(conn, "P", None, None)
    first = _session(conn, p, "2026-11-05T09:00:00+00:00", "2026-11-05T10:00:00+00:00")
    second = _session(conn, p, "2026-11-05T15:00:00+00:00", "2026-11-05T16:00:00+00:00")
    found = repositories.sessions_overlapping(conn, W_START, W_END)
    assert [r["id"] for r in found] == [first, second]