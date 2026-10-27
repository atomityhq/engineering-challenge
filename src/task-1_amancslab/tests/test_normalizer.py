"""Tests for URL normalisation."""

import pytest

from source_filter.models import SourceRecord
from source_filter.normalizer import (
    canonical_url_for,
    normalize_url,
)


def test_lowercases_scheme_and_hostname():
    assert normalize_url(
        "HTTPS://Example.COM/news"
    ) == "https://example.com/news"


def test_removes_fragment():
    assert normalize_url(
        "https://example.com/news#summary"
    ) == "https://example.com/news"


def test_removes_tracking_parameters():
    assert normalize_url(
        "https://example.com/news?id=123&utm_source=feed"
    ) == "https://example.com/news?id=123"


def test_preserves_meaningful_query_parameters():
    assert normalize_url(
        "https://example.com/news?id=123&category=security"
    ) == "https://example.com/news?id=123&category=security"


def test_removes_default_port_and_adds_root_path():
    assert normalize_url(
        "HTTP://Example.com:80"
    ) == "http://example.com/"


def test_rejects_non_http_url():
    with pytest.raises(ValueError):
        normalize_url("javascript:alert(1)")


def test_explicit_canonical_url_takes_precedence():
    record = SourceRecord(
        source_id="source-001",
        url="https://example.com/article?tracking=123",
        canonical_url="https://example.com/original",
    )

    assert canonical_url_for(record) == (
        "https://example.com/original"
    )


def test_falls_back_to_source_url():
    record = SourceRecord(
        source_id="source-002",
        url="https://Example.com/article#section",
    )

    assert canonical_url_for(record) == (
        "https://example.com/article"
    )