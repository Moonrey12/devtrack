from datetime import date, datetime, timedelta, timezone

import pytest

from devtrack.timeutils import (
    day_window,
    duration_seconds,
    format_duration,
    format_local,
    overlap_seconds,
    parse_iso,
    session_seconds_in_window,
    to_iso,
    utc_now,
    week_days,
    week_start,
    week_window,
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


def _utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_day_window_in_utc():
    start, end = day_window(date(2026, 11, 5), timezone.utc)
    assert (start, end) == (_utc(2026, 11, 5), _utc(2026, 11, 6))


def test_day_window_in_utc_plus_8_starts_the_previous_utc_afternoon():
    start, end = day_window(date(2026, 11, 5), UTC_PLUS_8)
    assert start == _utc(2026, 11, 4, 16)
    assert end == _utc(2026, 11, 5, 16)


@pytest.mark.parametrize(
    "day, next_day",
    [
        (date(2026, 11, 30), date(2026, 12, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
        (date(2028, 2, 29), date(2028, 3, 1)),
        (date(2027, 2, 28), date(2027, 3, 1)),
    ],
)
def test_day_window_crosses_month_year_and_leap_boundaries(day, next_day):
    start, end = day_window(day, timezone.utc)
    assert start == _utc(day.year, day.month, day.day)
    assert end == _utc(next_day.year, next_day.month, next_day.day)


def test_day_window_default_zone_is_exactly_one_local_day():
    start, end = day_window(date(2026, 11, 5))
    assert start.utcoffset() == timedelta(0)
    assert start.astimezone().strftime("%H:%M") == "00:00"
    assert end - start in (timedelta(hours=23), timedelta(hours=24), timedelta(hours=25))


def _zone_or_skip(name):
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        return zoneinfo.ZoneInfo(name)
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("time zone database (tzdata) is not installed")


def test_day_window_on_the_day_clocks_go_back_is_25_hours():
    new_york = _zone_or_skip("America/New_York")
    start, end = day_window(date(2026, 11, 1), new_york)
    assert end - start == timedelta(hours=25)


def test_day_window_on_the_day_clocks_go_forward_is_23_hours():
    new_york = _zone_or_skip("America/New_York")
    start, end = day_window(date(2026, 3, 8), new_york)
    assert end - start == timedelta(hours=23)


@pytest.mark.parametrize(
    "day, first_weekday, expected",
    [
        (date(2026, 11, 4), 0, date(2026, 11, 2)),   # Wednesday -> Monday
        (date(2026, 11, 2), 0, date(2026, 11, 2)),   # Monday stays
        (date(2026, 11, 8), 0, date(2026, 11, 2)),   # Sunday belongs to the Monday week
        (date(2026, 11, 8), 6, date(2026, 11, 8)),   # Sunday-start weeks: Sunday stays
        (date(2026, 11, 7), 6, date(2026, 11, 1)),   # Saturday -> previous Sunday
    ],
)
def test_week_start(day, first_weekday, expected):
    assert week_start(day, first_weekday) == expected


@pytest.mark.parametrize("bad", [-1, 7])
def test_week_start_rejects_bad_first_weekday(bad):
    with pytest.raises(ValueError):
        week_start(date(2026, 11, 4), bad)


def test_week_days_are_seven_consecutive_dates():
    days = week_days(date(2026, 11, 4))
    assert days[0] == date(2026, 11, 2) and days[-1] == date(2026, 11, 8)
    assert len(days) == 7


def test_week_window_in_utc_spans_seven_days():
    start, end = week_window(date(2026, 11, 4), timezone.utc)
    assert start == _utc(2026, 11, 2)
    assert end == _utc(2026, 11, 9)


def test_week_window_respects_time_zone():
    start, end = week_window(date(2026, 11, 4), UTC_PLUS_8)
    assert start == _utc(2026, 11, 1, 16)
    assert end == _utc(2026, 11, 8, 16)


WIN_START = _utc(2026, 11, 5, 0)
WIN_END = _utc(2026, 11, 6, 0)


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (_utc(2026, 11, 5, 9), _utc(2026, 11, 5, 10, 30), 5400),      # fully inside
        (_utc(2026, 11, 4, 20), _utc(2026, 11, 4, 22), 0),            # before the window
        (_utc(2026, 11, 6, 1), _utc(2026, 11, 6, 2), 0),              # after the window
        (_utc(2026, 11, 4, 23, 30), _utc(2026, 11, 5, 0, 30), 1800),  # crosses the start
        (_utc(2026, 11, 5, 23, 30), _utc(2026, 11, 6, 0, 30), 1800),  # crosses the end
        (_utc(2026, 11, 4, 12), _utc(2026, 11, 7, 12), 86400),        # spans the whole window
        (_utc(2026, 11, 4, 23), _utc(2026, 11, 5, 0), 0),             # ends exactly at the start
        (_utc(2026, 11, 6, 0), _utc(2026, 11, 6, 1), 0),              # starts exactly at the end
        (_utc(2026, 11, 5, 9), _utc(2026, 11, 5, 9), 0),              # zero length
    ],
)
def test_overlap_seconds(start, end, expected):
    assert overlap_seconds(start, end, WIN_START, WIN_END) == expected


def test_session_seconds_in_window_splits_a_midnight_session():
    started, ended = "2026-11-04T23:30:00+00:00", "2026-11-05T00:30:00+00:00"
    now = _utc(2026, 11, 10)
    assert session_seconds_in_window(started, ended, now, WIN_START, WIN_END) == 1800
    previous = (_utc(2026, 11, 4), _utc(2026, 11, 5))
    assert session_seconds_in_window(started, ended, now, *previous) == 1800


def test_running_session_counts_up_to_now():
    started = "2026-11-05T09:00:00+00:00"
    assert session_seconds_in_window(started, None, _utc(2026, 11, 5, 10), WIN_START, WIN_END) == 3600


def test_running_session_is_cut_off_at_the_end_of_the_window():
    started = "2026-11-05T22:00:00+00:00"
    assert session_seconds_in_window(started, None, _utc(2026, 11, 7), WIN_START, WIN_END) == 7200


def test_running_session_in_the_future_of_now_counts_nothing_in_an_earlier_window():
    started = "2026-11-05T09:00:00+00:00"
    assert session_seconds_in_window(started, None, _utc(2026, 11, 5, 10), _utc(2026, 11, 4), WIN_START) == 0