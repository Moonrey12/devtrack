from datetime import datetime, timedelta, timezone

import pytest

from devtrack.timeutils import (
    duration_seconds,
    format_duration,
    format_local,
    parse_iso,
    to_iso,
    utc_now,
)

UTC_PLUS_8 = timezone(timedelta(hours=8))


def test_utc_now_is_timezone_aware_utc():
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_to_iso_formats_utc_without_microseconds():
    moment = datetime(2026, 11, 2, 9, 0, 0, 123456, tzinfo=timezone.utc)
    assert to_iso(moment) == "2026-11-02T09:00:00+00:00"


def test_to_iso_converts_other_zones_to_utc():
    moment = datetime(2026, 11, 2, 8, 0, 0, tzinfo=UTC_PLUS_8)
    assert to_iso(moment) == "2026-11-02T00:00:00+00:00"


def test_to_iso_rejects_naive_datetime():
    with pytest.raises(ValueError):
        to_iso(datetime(2026, 11, 2, 9, 0, 0))


def test_parse_iso_round_trips():
    text = "2026-11-02T09:00:00+00:00"
    assert to_iso(parse_iso(text)) == text


def test_parse_iso_normalizes_to_utc():
    assert to_iso(parse_iso("2026-11-02T08:00:00+08:00")) == "2026-11-02T00:00:00+00:00"


def test_parse_iso_rejects_text_without_timezone():
    with pytest.raises(ValueError):
        parse_iso("2026-11-02T09:00:00")


def test_duration_seconds_between_two_times():
    assert duration_seconds("2026-11-02T09:00:00+00:00", "2026-11-02T10:30:00+00:00") == 5400


def test_duration_seconds_same_time_is_zero():
    assert duration_seconds("2026-11-02T09:00:00+00:00", "2026-11-02T09:00:00+00:00") == 0


def test_duration_seconds_is_correct_across_time_zones():
    # 08:00 at UTC+8 is 00:00 UTC, so the gap to 01:00 UTC is exactly one hour.
    assert duration_seconds("2026-11-02T08:00:00+08:00", "2026-11-02T01:00:00+00:00") == 3600


def test_duration_seconds_rejects_end_before_start():
    with pytest.raises(ValueError):
        duration_seconds("2026-11-02T10:00:00+00:00", "2026-11-02T09:00:00+00:00")


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0s"),
        (59, "59s"),
        (60, "1m 0s"),
        (125, "2m 5s"),
        (3599, "59m 59s"),
        (3600, "1h 0m 0s"),
        (5025, "1h 23m 45s"),
        (86400, "24h 0m 0s"),
    ],
)
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_duration_rejects_negative():
    with pytest.raises(ValueError):
        format_duration(-1)


def test_format_local_shifts_into_the_given_zone():
    assert format_local("2026-11-02T09:00:00+00:00", UTC_PLUS_8) == "2026-11-02 17:00"


def test_format_local_can_cross_midnight():
    assert format_local("2026-11-02T20:30:00+00:00", UTC_PLUS_8) == "2026-11-03 04:30"


def test_format_local_in_utc_changes_nothing():
    assert format_local("2026-11-02T09:00:00+00:00", timezone.utc) == "2026-11-02 09:00"