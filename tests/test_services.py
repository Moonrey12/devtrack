from datetime import datetime, timezone

import pytest

from devtrack import repositories, services
from devtrack.services import ServiceError

T0 = datetime(2026, 11, 2, 9, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 11, 2, 11, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def project_id(conn):
    return repositories.add_project(conn, "Portfolio", None, None)


def test_start_session_makes_it_active(conn, project_id):
    session_id = services.start_session(conn, project_id, None, T0)
    active = repositories.get_active_session(conn)
    assert active["id"] == session_id
    assert active["started_at"] == "2026-11-02T09:00:00+00:00"


def test_start_session_for_missing_project_is_refused(conn):
    with pytest.raises(ServiceError, match="No project with id 99"):
        services.start_session(conn, 99, None, T0)


def test_start_session_for_missing_task_is_refused(conn, project_id):
    with pytest.raises(ServiceError, match="No task with id 99"):
        services.start_session(conn, project_id, 99, T0)


def test_start_session_with_task_from_another_project_is_refused(conn, project_id):
    other = repositories.add_project(conn, "Other", None, None)
    task_id = repositories.add_task(conn, other, "Not mine")
    with pytest.raises(ServiceError, match="does not belong"):
        services.start_session(conn, project_id, task_id, T0)
    assert repositories.get_active_session(conn) is None


def test_start_session_with_matching_task_works(conn, project_id):
    task_id = repositories.add_task(conn, project_id, "Write code")
    services.start_session(conn, project_id, task_id, T0)
    assert repositories.get_active_session(conn)["task_title"] == "Write code"


def test_cannot_start_while_another_session_is_running(conn, project_id):
    services.start_session(conn, project_id, None, T0)
    with pytest.raises(ServiceError, match="already running on 'Portfolio'"):
        services.start_session(conn, project_id, None, T1)


def test_can_start_again_after_stopping(conn, project_id):
    services.start_session(conn, project_id, None, T0)
    services.stop_session(conn, T1)
    services.start_session(conn, project_id, None, T1)
    assert repositories.get_active_session(conn) is not None


def test_database_lock_is_reported_as_a_friendly_error(conn, project_id, monkeypatch):
    # Simulate another terminal winning the race: our check sees nothing running,
    # but the database lock still stops the insert.
    services.start_session(conn, project_id, None, T0)
    monkeypatch.setattr(repositories, "get_active_session", lambda c: None)
    with pytest.raises(ServiceError, match="already running"):
        services.start_session(conn, project_id, None, T1)


def test_stop_session_returns_duration_and_names(conn, project_id):
    task_id = repositories.add_task(conn, project_id, "Write code")
    services.start_session(conn, project_id, task_id, T0)
    result = services.stop_session(conn, T1)
    assert result.seconds == 5400
    assert result.project_name == "Portfolio"
    assert result.task_title == "Write code"
    assert result.ended_at == "2026-11-02T10:30:00+00:00"
    assert result.running is False
    assert repositories.get_active_session(conn) is None


def test_stop_without_a_running_session_is_refused(conn):
    with pytest.raises(ServiceError, match="No session is running"):
        services.stop_session(conn, T1)


def test_stop_when_clock_is_before_start_is_refused_and_session_keeps_running(conn, project_id):
    services.start_session(conn, project_id, None, T1)
    with pytest.raises(ServiceError, match="clock"):
        services.stop_session(conn, T0)
    assert repositories.get_active_session(conn) is not None


def test_stop_reports_error_if_session_was_stopped_elsewhere(conn, project_id, monkeypatch):
    services.start_session(conn, project_id, None, T0)
    monkeypatch.setattr(repositories, "stop_session", lambda c, sid, end: False)
    with pytest.raises(ServiceError, match="No session is running"):
        services.stop_session(conn, T1)


def test_current_session_is_none_when_nothing_runs(conn):
    assert services.current_session(conn, T0) is None


def test_current_session_shows_elapsed_time_so_far(conn, project_id):
    services.start_session(conn, project_id, None, T0)
    status = services.current_session(conn, T1)
    assert status.running is True
    assert status.seconds == 5400
    assert status.ended_at is None


def test_recent_sessions_newest_first_with_durations(conn, project_id):
    services.start_session(conn, project_id, None, T0)
    services.stop_session(conn, T1)
    services.start_session(conn, project_id, None, T1)
    records = services.recent_sessions(conn, T2)
    assert [r.running for r in records] == [True, False]
    assert [r.seconds for r in records] == [1800, 5400]


def test_recent_sessions_respects_limit(conn, project_id):
    services.start_session(conn, project_id, None, T0)
    services.stop_session(conn, T1)
    services.start_session(conn, project_id, None, T1)
    assert len(services.recent_sessions(conn, T2, limit=1)) == 1