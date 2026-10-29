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