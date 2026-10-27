"""Reusable scalar checks shared by parsing and contract construction."""

from datetime import date
from enum import Enum
from typing import TypeVar

from .errors import ValidationError

EnumType = TypeVar("EnumType", bound=Enum)


def require_text(value: object, path: str) -> str:
    """Require non-blank text without trimming or coercing it."""
    if type(value) is not str:
        raise ValidationError("INVALID_TYPE", path, "Expected a string.")
    if not value.strip():
        raise ValidationError("EMPTY_STRING", path, "Expected non-blank text.")
    return value


def require_bool(value: object, path: str) -> bool:
    """Require an actual boolean rather than a truthy value."""
    if type(value) is not bool:
        raise ValidationError("INVALID_TYPE", path, "Expected a boolean.")
    return value


def require_date(value: object, path: str) -> date | None:
    """Require an exact date instance or explicit unknown value."""
    if value is not None and type(value) is not date:
        raise ValidationError("INVALID_TYPE", path, "Expected a date or null.")
    return value


def require_enum(value: object, enum_type: type[EnumType], path: str) -> EnumType:
    """Require the declared enum, including its recognized unknown member."""
    if type(value) is not enum_type:
        raise ValidationError("INVALID_TYPE", path, "Expected the declared enum.")
    return value
