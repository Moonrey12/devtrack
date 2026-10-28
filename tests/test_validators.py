import pytest

from devtrack.validators import (
    ValidationError,
    validate_name,
    validate_optional_text,
    validate_title,
)


def test_validate_name_strips_whitespace():
    assert validate_name("  Portfolio  ") == "Portfolio"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_validate_name_rejects_empty(value):
    with pytest.raises(ValidationError):
        validate_name(value)


def test_validate_name_accepts_exactly_100_characters():
    assert validate_name("a" * 100) == "a" * 100


def test_validate_name_rejects_101_characters():
    with pytest.raises(ValidationError, match="too long"):
        validate_name("a" * 101)


@pytest.mark.parametrize("value", ["", "   "])
def test_validate_title_rejects_empty(value):
    with pytest.raises(ValidationError):
        validate_title(value)


def test_validate_title_length_boundary():
    assert validate_title("t" * 200) == "t" * 200
    with pytest.raises(ValidationError):
        validate_title("t" * 201)


def test_optional_text_none_stays_none():
    assert validate_optional_text(None, "Description") is None


def test_optional_text_blank_becomes_none():
    assert validate_optional_text("   ", "Description") is None


@pytest.mark.parametrize("raw, expected", [(" a ", "a"), ("b  ", "b"), ("c", "c")])
def test_optional_text_strips(raw, expected):
    assert validate_optional_text(raw, "Description") == expected


def test_optional_text_rejects_too_long():
    with pytest.raises(ValidationError):
        validate_optional_text("x" * 501, "Description")
    with pytest.raises(ValidationError):
        validate_optional_text("xyz", "Tech stack", max_length=2)