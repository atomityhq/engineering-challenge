"""Strict, pure JSON parsing and label-free input boundary validation."""

from datetime import date
from enum import Enum
import json
import math
import re
from typing import TypeAlias, TypeVar, cast

from ._checks import require_bool, require_text
from .contracts import (
    BOOLEAN_FIELDS,
    DATE_FIELDS,
    ContentType,
    CurrentStatus,
    EvaluationCase,
    Metadata,
    SourceType,
)
from .errors import ValidationError

JSONValue: TypeAlias = (
    str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
)
EnumType = TypeVar("EnumType", bound=Enum)
_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_METADATA_FIELDS: tuple[str, ...] = (
    "source_type", "content_type", *DATE_FIELDS, "current_status", *BOOLEAN_FIELDS
)


def _unique_object(pairs: list[tuple[str, JSONValue]]) -> dict[str, JSONValue]:
    result: dict[str, JSONValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(
                "DUPLICATE_KEY", "$", "JSON object contains a repeated key."
            )
        result[key] = value
    return result


def _reject_constant(token: str) -> JSONValue:
    raise ValidationError(
        "NON_FINITE_NUMBER", "$", "JSON numbers must be finite."
    )


def _finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValidationError(
            "NON_FINITE_NUMBER", "$", "JSON numbers must be finite."
        )
    return value


def parse_json(text: str) -> JSONValue:
    """Decode JSON, rejecting duplicate keys and non-finite numbers.

    Decoder failures use the document path because standard-library hooks do
    not expose nested paths. Raw input and decoder messages are not exposed.
    """
    if type(text) is not str:
        raise ValidationError("INVALID_TYPE", "$", "Expected JSON text.")
    try:
        return cast(
            JSONValue,
            json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
                parse_float=_finite_float,
            ),
        )
    except ValidationError:
        raise
    except json.JSONDecodeError:
        raise ValidationError("INVALID_JSON", "$", "Malformed JSON document.") from None
    except (ValueError, RecursionError):
        raise ValidationError(
            "INVALID_JSON", "$", "JSON document exceeds decoder limits."
        ) from None


def require_object(
    value: object, fields: tuple[str, ...], path: str
) -> dict[str, object]:
    """Require an exact object shape without exposing unknown keys or values."""
    if type(value) is not dict:
        raise ValidationError("INVALID_TYPE", path, "Expected a JSON object.")
    for field in fields:
        if field not in value:
            raise ValidationError(
                "MISSING_FIELD", f"{path}.{field}", "Required field is missing."
            )
    if any(type(key) is not str or key not in fields for key in value):
        raise ValidationError("UNKNOWN_FIELD", path, "Unexpected field in object.")
    return cast(dict[str, object], value)


def parse_date(value: object, path: str) -> date | None:
    """Parse exact ASCII YYYY-MM-DD calendar dates or explicit null."""
    if value is None:
        return None
    if type(value) is not str:
        raise ValidationError("INVALID_TYPE", path, "Expected a date string or null.")
    if _DATE_PATTERN.fullmatch(value) is None:
        raise ValidationError("INVALID_DATE", path, "Expected YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError("INVALID_DATE", path, "Invalid calendar date.") from None


def _parse_enum(value: object, enum_type: type[EnumType], path: str) -> EnumType:
    text = require_text(value, path)
    try:
        return enum_type(text)
    except ValueError:
        raise ValidationError(
            "INVALID_ENUM", path, "Unrecognized category."
        ) from None


def validate_metadata(value: object, path: str = "$.metadata") -> Metadata:
    """Validate every metadata key without coercion or temporal inference."""
    data = require_object(value, _METADATA_FIELDS, path)
    return Metadata(
        source_type=_parse_enum(data["source_type"], SourceType, f"{path}.source_type"),
        content_type=_parse_enum(data["content_type"], ContentType, f"{path}.content_type"),
        published_at=parse_date(data["published_at"], f"{path}.published_at"),
        event_date=parse_date(data["event_date"], f"{path}.event_date"),
        effective_from=parse_date(data["effective_from"], f"{path}.effective_from"),
        last_verified_at=parse_date(data["last_verified_at"], f"{path}.last_verified_at"),
        current_status=_parse_enum(
            data["current_status"], CurrentStatus, f"{path}.current_status"
        ),
        supported=require_bool(data["supported"], f"{path}.supported"),
        superseded=require_bool(data["superseded"], f"{path}.superseded"),
        contradiction=require_bool(data["contradiction"], f"{path}.contradiction"),
        competitor_product_claim=require_bool(
            data["competitor_product_claim"], f"{path}.competitor_product_claim"
        ),
    )


def validate_case(value: object, path: str = "$") -> EvaluationCase:
    """Build a label-free case, rejecting missing, extra, and invalid fields."""
    data = require_object(value, ("id", "statement", "metadata"), path)
    return EvaluationCase(
        id=require_text(data["id"], f"{path}.id"),
        statement=require_text(data["statement"], f"{path}.statement"),
        metadata=validate_metadata(data["metadata"], f"{path}.metadata"),
    )
