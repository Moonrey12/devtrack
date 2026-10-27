"""Input validation helpers: they check and clean values, never print or touch the DB."""

MAX_NAME_LENGTH = 100
MAX_TITLE_LENGTH = 200
MAX_TEXT_LENGTH = 500


class ValidationError(Exception):
    """Raised when user input is invalid; the message is safe to show to the user."""


def _check_length(value: str, label: str, max_length: int) -> None:
    """Raise ValidationError if value is longer than max_length."""
    if len(value) > max_length:
        raise ValidationError(
            f"{label} is too long ({len(value)} characters; maximum is {max_length})."
        )


def validate_name(value: str) -> str:
    """Return the project name stripped of whitespace, or raise ValidationError."""
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError("Project name cannot be empty.")
    _check_length(cleaned, "Project name", MAX_NAME_LENGTH)
    return cleaned


def validate_title(value: str) -> str:
    """Return the task title stripped of whitespace, or raise ValidationError."""
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError("Task title cannot be empty.")
    _check_length(cleaned, "Task title", MAX_TITLE_LENGTH)
    return cleaned


def validate_optional_text(
    value: str | None, label: str, max_length: int = MAX_TEXT_LENGTH
) -> str | None:
    """Return None for missing or blank text, otherwise the stripped text."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    _check_length(cleaned, label, max_length)
    return cleaned