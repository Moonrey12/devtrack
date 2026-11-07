"""Time helpers: times are stored as UTC ISO-8601 text and shown in local time."""

from datetime import date, datetime, timedelta, timezone, tzinfo


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_iso(moment: datetime) -> str:
    """Convert an aware datetime to UTC ISO text without microseconds."""
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(text: str) -> datetime:
    """Parse stored ISO text into an aware UTC datetime."""
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(f"time '{text}' has no timezone")
    return moment.astimezone(timezone.utc)


def duration_seconds(started_at: str, ended_at: str) -> int:
    """Return whole seconds between two stored times (never negative)."""
    seconds = int((parse_iso(ended_at) - parse_iso(started_at)).total_seconds())
    if seconds < 0:
        raise ValueError("ended_at is before started_at")
    return seconds


def format_duration(total_seconds: int) -> str:
    """Format seconds as '1h 23m 45s', '2m 5s', or '45s'."""
    if total_seconds < 0:
        raise ValueError("duration cannot be negative")
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def format_local(text: str, tz: tzinfo | None = None) -> str:
    """Show a stored UTC time as 'YYYY-MM-DD HH:MM' in tz (default: the computer's zone)."""
    return parse_iso(text).astimezone(tz).strftime("%Y-%m-%d %H:%M")

def _local_midnight(day: date, tz: tzinfo | None) -> datetime:
    """Return midnight at the start of `day` as an aware datetime in `tz` (None = computer's zone)."""
    midnight = datetime(day.year, day.month, day.day)
    if tz is None:
        return midnight.astimezone()  # a naive time is read as the computer's local time
    return midnight.replace(tzinfo=tz)


def day_window(day: date, tz: tzinfo | None = None) -> tuple[datetime, datetime]:
    """Return the UTC [start, end) window covering one local calendar day."""
    start = _local_midnight(day, tz)
    end = _local_midnight(day + timedelta(days=1), tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def week_start(day: date, first_weekday: int = 0) -> date:
    """Return the first day of the week containing `day` (0=Monday ... 6=Sunday)."""
    if not 0 <= first_weekday <= 6:
        raise ValueError("first_weekday must be between 0 (Monday) and 6 (Sunday)")
    return day - timedelta(days=(day.weekday() - first_weekday) % 7)


def week_days(day: date, first_weekday: int = 0) -> list[date]:
    """Return the seven dates of the week containing `day`."""
    first = week_start(day, first_weekday)
    return [first + timedelta(days=offset) for offset in range(7)]


def week_window(
    day: date, tz: tzinfo | None = None, first_weekday: int = 0
) -> tuple[datetime, datetime]:
    """Return the UTC [start, end) window covering the whole local week containing `day`."""
    days = week_days(day, first_weekday)
    return day_window(days[0], tz)[0], day_window(days[-1], tz)[1]


def overlap_seconds(
    start: datetime, end: datetime, window_start: datetime, window_end: datetime
) -> int:
    """Return whole seconds of [start, end) that fall inside [window_start, window_end)."""
    latest_start = max(start, window_start)
    earliest_end = min(end, window_end)
    return max(0, int((earliest_end - latest_start).total_seconds()))


def session_seconds_in_window(
    started_at: str,
    ended_at: str | None,
    now: datetime,
    window_start: datetime,
    window_end: datetime,
) -> int:
    """Seconds of a stored session inside a window; a running session counts up to `now`."""
    end = now if ended_at is None else parse_iso(ended_at)
    return overlap_seconds(parse_iso(started_at), end, window_start, window_end)

def to_sqlite_text(moment: datetime) -> str:
    """Format an aware datetime like SQLite's datetime('now'): 'YYYY-MM-DD HH:MM:SS' in UTC."""
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")