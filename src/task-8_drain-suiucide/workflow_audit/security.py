"""Small deterministic redaction helpers for audit-boundary data."""

from __future__ import annotations

import re
from typing import Any

_REDACT_ASSIGNMENT = re.compile(
    r"(?i)([A-Z0-9_-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)[A-Z0-9_-]*\s*[=:]\s*)([^\s,;]+)"
)
_REDACT_BEARER = re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]+")


def redact_text(value: str) -> str:
    """Redact common credential-like assignments without altering other text."""
    value = _REDACT_ASSIGNMENT.sub(r"\1[REDACTED]", value)
    value = _REDACT_BEARER.sub(r"\1[REDACTED]", value)
    return value


def redact(value: Any) -> Any:
    """Return a redacted copy of nested JSON-compatible data."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    return value
