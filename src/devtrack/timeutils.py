"""Time helpers: times are stored as UTC ISO-8601 text and shown in local time."""

from datetime import datetime, timezone, tzinfo


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