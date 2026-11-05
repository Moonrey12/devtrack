from datetime import datetime, timezone

import pytest

from devtrack.cli import main
import pytest

from devtrack.cli import main


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point every CLI test at its own throwaway database file."""
    monkeypatch.setenv("DEVTRACK_DB", str(tmp_path / "test.db"))


def test_add_and_list_project(capsys):
    assert main(["project", "add", "Portfolio", "-t", "Python"]) == 0
    assert main(["project", "list"]) == 0
    assert "Portfolio" in capsys.readouterr().out


def test_duplicate_project_returns_1(capsys):
    main(["project", "add", "Portfolio"])
    assert main(["project", "add", "Portfolio"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_show_missing_project_returns_1(capsys):
    assert main(["project", "show", "99"]) == 1
    assert "no project with id 99" in capsys.readouterr().err


def test_empty_project_name_returns_1(capsys):
    assert main(["project", "add", "   "]) == 1
    assert "cannot be empty" in capsys.readouterr().err


@pytest.mark.parametrize("bad_id", ["0", "-5", "abc"])
def test_bad_project_id_is_usage_error(bad_id):
    with pytest.raises(SystemExit) as exc:
        main(["project", "show", bad_id])
    assert exc.value.code == 2


def test_invalid_status_filter_exits_with_2():
    with pytest.raises(SystemExit) as exc:
        main(["task", "list", "1", "--status", "banana"])
    assert exc.value.code == 2


def test_task_flow_add_status_list(capsys):
    main(["project", "add", "Portfolio"])
    assert main(["task", "add", "1", "Design schema"]) == 0
    assert main(["task", "status", "1", "completed"]) == 0
    capsys.readouterr()
    assert main(["task", "list", "1", "--status", "completed"]) == 0
    assert "Design schema" in capsys.readouterr().out


def test_task_add_for_missing_project_returns_1(capsys):
    assert main(["task", "add", "99", "Oops"]) == 1
    assert "no project with id 99" in capsys.readouterr().err


def test_delete_cancelled_keeps_task(monkeypatch, capsys):
    main(["project", "add", "P"])
    main(["task", "add", "1", "Keep me"])
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert main(["task", "delete", "1"]) == 0
    capsys.readouterr()
    main(["task", "list", "1"])
    assert "Keep me" in capsys.readouterr().out


def test_delete_confirmed_and_yes_flag(monkeypatch, capsys):
    main(["project", "add", "P"])
    main(["task", "add", "1", "One"])
    main(["task", "add", "1", "Two"])
    monkeypatch.setattr("builtins.input", lambda _prompt: "y")
    assert main(["task", "delete", "1"]) == 0
    assert main(["task", "delete", "2", "--yes"]) == 0
    capsys.readouterr()
    main(["task", "list", "1"])
    assert "No tasks" in capsys.readouterr().out


def test_data_persists_between_runs(capsys):
    main(["project", "add", "Persistent"])
    capsys.readouterr()
    assert main(["project", "list"]) == 0
    assert "Persistent" in capsys.readouterr().out


def test_no_arguments_prints_help_and_returns_1(capsys):
    assert main([]) == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_add_task_with_priority_and_deadline_shows_in_list(capsys):
    main(["project", "add", "P"])
    assert main(["task", "add", "1", "Ship it", "--priority", "high", "--deadline", "2026-12-31"]) == 0
    capsys.readouterr()
    assert main(["task", "list", "1"]) == 0
    out = capsys.readouterr().out
    assert "high" in out and "2026-12-31" in out and "Ship it" in out


def test_task_without_priority_shows_dashes(capsys):
    main(["project", "add", "P"])
    main(["task", "add", "1", "Plain"])
    capsys.readouterr()
    main(["task", "list", "1"])
    row = [line for line in capsys.readouterr().out.splitlines() if "Plain" in line][0]
    assert row.count("-") >= 2


def test_bad_deadline_returns_1(capsys):
    main(["project", "add", "P"])
    assert main(["task", "add", "1", "x", "--deadline", "2026-02-30"]) == 1
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_bad_priority_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["task", "add", "1", "x", "--priority", "urgent"])
    assert exc.value.code == 2


def test_task_edit_changes_and_clears(capsys):
    main(["project", "add", "P"])
    main(["task", "add", "1", "x", "--priority", "low", "--deadline", "2026-11-30"])
    capsys.readouterr()
    assert main(["task", "edit", "1", "--priority", "high"]) == 0
    assert "priority=high" in capsys.readouterr().out
    assert main(["task", "edit", "1", "--deadline", "none"]) == 0
    out = capsys.readouterr().out
    assert "priority=high" in out and "deadline=-" in out


def test_task_edit_needs_something_to_change(capsys):
    main(["project", "add", "P"])
    main(["task", "add", "1", "x"])
    assert main(["task", "edit", "1"]) == 1
    assert "nothing to change" in capsys.readouterr().err


def test_task_edit_missing_task_returns_1(capsys):
    assert main(["task", "edit", "99", "--priority", "high"]) == 1
    assert "no task with id 99" in capsys.readouterr().err


def _seed_for_search():
    main(["project", "add", "Alpha"])
    main(["project", "add", "Beta"])
    main(["task", "add", "1", "Fix login bug", "--priority", "high", "--deadline", "2000-01-01"])
    main(["task", "add", "1", "Write docs", "--priority", "low", "--deadline", "2999-01-01"])
    main(["task", "add", "2", "Deploy app", "--priority", "high", "--deadline", "2000-06-01"])
    main(["task", "add", "2", "Old finished job", "--deadline", "2000-02-01"])
    main(["task", "status", "4", "completed"])


def test_search_finds_tasks_across_projects_with_project_names(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search", "app"]) == 0
    out = capsys.readouterr().out
    assert "Deploy app" in out and "Beta" in out
    assert "1 task(s) found." in out


def test_search_without_arguments_lists_every_task(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search"]) == 0
    assert "4 task(s) found." in capsys.readouterr().out


def test_search_filters_by_priority_and_project(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search", "--priority", "high", "--project", "2"]) == 0
    out = capsys.readouterr().out
    assert "Deploy app" in out
    assert "Fix login bug" not in out  # wrong project
    assert "Old finished job" not in out  # right project, but not high priority
    assert "1 task(s) found." in out


def test_search_overdue_excludes_completed_and_future(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search", "--overdue"]) == 0
    out = capsys.readouterr().out
    assert "Fix login bug" in out and "Deploy app" in out
    assert "Write docs" not in out and "Old finished job" not in out


def test_search_sort_by_deadline_orders_output(capsys):
    _seed_for_search()
    capsys.readouterr()
    main(["task", "search", "--sort", "deadline"])
    out = capsys.readouterr().out
    assert out.index("Fix login bug") < out.index("Old finished job") < out.index("Deploy app")
    assert out.index("Deploy app") < out.index("Write docs")


def test_search_with_no_matches_prints_message_and_returns_0(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search", "zzz"]) == 0
    assert "No matching tasks." in capsys.readouterr().out


def test_search_unknown_project_returns_1(capsys):
    assert main(["task", "search", "--project", "99"]) == 1
    assert "no project with id 99" in capsys.readouterr().err


def test_search_bad_due_by_returns_1(capsys):
    assert main(["task", "search", "--due-by", "2026-02-30"]) == 1
    assert "YYYY-MM-DD" in capsys.readouterr().err


def test_search_due_by_filters(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search", "--due-by", "2000-03-01"]) == 0
    out = capsys.readouterr().out
    assert "Fix login bug" in out and "Old finished job" in out
    assert "Write docs" not in out


def test_search_bad_sort_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["task", "search", "--sort", "nope"])
    assert exc.value.code == 2
    assert "argument --sort" in capsys.readouterr().err


def test_search_filters_by_status(capsys):
    _seed_for_search()
    capsys.readouterr()
    assert main(["task", "search", "--status", "completed"]) == 0
    out = capsys.readouterr().out
    assert "Old finished job" in out
    assert "Fix login bug" not in out
    assert "1 task(s) found." in out

def _at(monkeypatch, hour, minute=0):
    """Freeze the CLI's clock at 2026-11-02 HH:MM UTC."""
    moment = datetime(2026, 11, 2, hour, minute, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("devtrack.cli.utc_now", lambda: moment)


def test_session_start_status_stop_flow(monkeypatch, capsys):
    main(["project", "add", "Portfolio"])
    _at(monkeypatch, 9)
    assert main(["session", "start", "1"]) == 0
    assert "Started session on 'Portfolio'" in capsys.readouterr().out

    _at(monkeypatch, 10, 30)
    assert main(["session", "status"]) == 0
    status_out = capsys.readouterr().out
    assert "Running on 'Portfolio'" in status_out and "1h 30m 0s so far" in status_out

    _at(monkeypatch, 11)
    assert main(["session", "stop"]) == 0
    stop_out = capsys.readouterr().out
    assert "Stopped session on 'Portfolio'" in stop_out and "Worked 2h 0m 0s" in stop_out

    assert main(["session", "status"]) == 0
    assert "No session is running." in capsys.readouterr().out


def test_session_start_with_task_shows_task_title(monkeypatch, capsys):
    main(["project", "add", "Portfolio"])
    main(["task", "add", "1", "Write docs"])
    _at(monkeypatch, 9)
    capsys.readouterr()
    assert main(["session", "start", "1", "--task", "1"]) == 0
    assert "(task: Write docs)" in capsys.readouterr().out


def test_session_start_unknown_project_returns_1(monkeypatch, capsys):
    _at(monkeypatch, 9)
    assert main(["session", "start", "99"]) == 1
    assert "No project with id 99" in capsys.readouterr().err


def test_session_start_task_from_other_project_returns_1(monkeypatch, capsys):
    main(["project", "add", "A"])
    main(["project", "add", "B"])
    main(["task", "add", "2", "Not in A"])
    _at(monkeypatch, 9)
    capsys.readouterr()
    assert main(["session", "start", "1", "--task", "1"]) == 1
    assert "does not belong" in capsys.readouterr().err


def test_session_cannot_start_twice(monkeypatch, capsys):
    main(["project", "add", "Portfolio"])
    _at(monkeypatch, 9)
    assert main(["session", "start", "1"]) == 0
    capsys.readouterr()
    assert main(["session", "start", "1"]) == 1
    assert "already running on 'Portfolio'" in capsys.readouterr().err


def test_session_stop_without_running_session_returns_1(monkeypatch, capsys):
    _at(monkeypatch, 9)
    assert main(["session", "stop"]) == 1
    assert "No session is running." in capsys.readouterr().err


def test_session_list_shows_durations_and_running_marker(monkeypatch, capsys):
    main(["project", "add", "Portfolio"])
    _at(monkeypatch, 9)
    main(["session", "start", "1"])
    _at(monkeypatch, 10, 30)
    main(["session", "stop"])
    _at(monkeypatch, 11)
    main(["session", "start", "1"])
    _at(monkeypatch, 11, 20)
    capsys.readouterr()
    assert main(["session", "list"]) == 0
    out = capsys.readouterr().out
    assert "1h 30m 0s" in out
    assert "20m 0s (running)" in out
    assert out.index("(running)") < out.index("1h 30m 0s")  # newest first


def test_session_list_empty_prints_hint(monkeypatch, capsys):
    _at(monkeypatch, 9)
    assert main(["session", "list"]) == 0
    assert "No sessions yet" in capsys.readouterr().out


def test_session_list_limit(monkeypatch, capsys):
    main(["project", "add", "Portfolio"])
    for hour in (9, 11, 13):
        _at(monkeypatch, hour)
        main(["session", "start", "1"])
        _at(monkeypatch, hour + 1)
        main(["session", "stop"])
    capsys.readouterr()
    assert main(["session", "list", "--limit", "2"]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if "Portfolio" in ln]
    assert len(lines) == 2


@pytest.mark.parametrize(
    "args, argument",
    [
        (["session", "start", "0"], "project_id"),
        (["session", "list", "--limit", "0"], "--limit"),
    ],
)
def test_session_bad_numbers_are_usage_errors(args, argument, capsys):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert f"argument {argument}: id must be 1 or greater" in capsys.readouterr().err


def test_session_without_action_prints_help_and_returns_1(capsys):
    assert main(["session"]) == 1
    assert "usage" in capsys.readouterr().out.lower()