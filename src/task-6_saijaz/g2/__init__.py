"""Dependency-free G2 contracts and strict input validation."""

from .contracts import ContentType, CurrentStatus, EvaluationCase, Metadata, SourceType
from .errors import ValidationError, ValidationIssue
from .validation import parse_json, validate_case, validate_metadata

__all__ = [
    "ContentType",
    "CurrentStatus",
    "EvaluationCase",
    "Metadata",
    "SourceType",
    "ValidationError",
    "ValidationIssue",
    "parse_json",
    "validate_case",
    "validate_metadata",
]
