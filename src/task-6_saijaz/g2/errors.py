"""Safe structured errors for invalid external input and contracts."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Describe a validation failure without including raw input values."""

    code: str
    path: str
    message: str

    def __post_init__(self) -> None:
        for value in (self.code, self.path, self.message):
            if type(value) is not str or not value.strip():
                raise ValueError("Validation issue fields must be non-empty strings.")


class ValidationError(ValueError):
    """Expose a stable issue for malformed input or invalid construction."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.issue = ValidationIssue(code=code, path=path, message=message)
        super().__init__(f"{code} at {path}: {message}")
