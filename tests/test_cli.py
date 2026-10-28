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