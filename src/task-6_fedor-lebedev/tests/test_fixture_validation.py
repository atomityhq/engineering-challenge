"""Malformed or incomplete fixtures fail with a predictable, located error."""

import json

import pytest

from g2_gate.cli import main
from g2_gate.loading import InputValidationError, load_fixture, validate
from g2_gate.models import G2Fixture
from g2_gate.paths import WEIGHTING_FIXTURE

METADATA_FIELDS = [
    "source_type", "content_type", "published_at", "event_date", "effective_from", "last_verified_at",
    "current_status", "supported", "superseded", "contradiction", "competitor_product_claim",
]


def check(data):
    return validate(data, G2Fixture, "test-fixture")


def problems_of(data):
    with pytest.raises(InputValidationError) as info:
        check(data)
    return info.value.problems


def test_supplied_fixture_is_valid(starter):
    assert starter.as_of.isoformat() == "2026-10-06"
    assert starter.synthetic is True
    assert len(starter.cases) == 9


@pytest.mark.parametrize("field", METADATA_FIELDS)
def test_missing_metadata_field_is_a_validation_failure(starter_raw, field):
    del starter_raw["cases"][2]["metadata"][field]
    assert f"cases.2.metadata.{field}: Field required" in problems_of(starter_raw)


@pytest.mark.parametrize("field", ["schema_version", "synthetic", "as_of", "demo_policy", "cases"])
def test_missing_envelope_field_is_a_validation_failure(starter_raw, field):
    del starter_raw[field]
    assert f"{field}: Field required" in problems_of(starter_raw)


@pytest.mark.parametrize("field", ["id", "statement", "metadata"])
def test_missing_case_field_is_a_validation_failure(starter_raw, field):
    del starter_raw["cases"][0][field]
    assert f"cases.0.{field}: Field required" in problems_of(starter_raw)


def test_missing_demo_policy_window_is_a_validation_failure(starter_raw):
    del starter_raw["demo_policy"]["news_max_event_age_days"]
    assert "demo_policy.news_max_event_age_days: Field required" in problems_of(starter_raw)


@pytest.mark.parametrize("value", ["06/10/2026", "2026-10-06T00:00:00", "20261006", "2026-02-30", 20261006])
def test_dates_must_be_iso_calendar_dates(starter_raw, value):
    starter_raw["cases"][0]["metadata"]["event_date"] = value
    assert any(p.startswith("cases.0.metadata.event_date") for p in problems_of(starter_raw))


def test_as_of_is_required_to_be_a_real_date(starter_raw):
    starter_raw["as_of"] = None
    assert any(p.startswith("as_of") for p in problems_of(starter_raw))


@pytest.mark.parametrize("field, value", [
    ("source_type", "blog"),
    ("content_type", "podcast"),
    ("current_status", "probably"),
    ("supported", "true"),
    ("superseded", 0),
    ("contradiction", None),
    ("competitor_product_claim", "no"),
])
def test_wrongly_typed_metadata_is_rejected(starter_raw, field, value):
    starter_raw["cases"][0]["metadata"][field] = value
    assert any(p.startswith(f"cases.0.metadata.{field}") for p in problems_of(starter_raw))


def test_misspelled_metadata_key_is_not_ignored(starter_raw):
    starter_raw["cases"][0]["metadata"]["superseeded"] = True
    assert any("superseeded" in p for p in problems_of(starter_raw))


def test_duplicate_case_ids_are_rejected(starter_raw):
    starter_raw["cases"][1]["id"] = starter_raw["cases"][0]["id"]
    assert any("duplicate case ids: current-news" in p for p in problems_of(starter_raw))


def test_empty_case_list_is_rejected(starter_raw):
    starter_raw["cases"] = []
    assert any(p.startswith("cases") for p in problems_of(starter_raw))


def test_unknown_values_are_allowed_where_unknown_is_meaningful(starter_raw):
    metadata = starter_raw["cases"][0]["metadata"]
    metadata.update(event_date=None, published_at=None, last_verified_at=None, supported=None)
    case = check(starter_raw).cases[0]
    assert case.metadata.event_date is None and case.metadata.supported is None


def test_unreadable_and_non_json_files_fail_predictably(tmp_path):
    with pytest.raises(InputValidationError, match="cannot read file"):
        load_fixture(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{\"cases\": [", encoding="utf-8")
    with pytest.raises(InputValidationError, match="invalid JSON"):
        load_fixture(broken)


def test_cli_reports_malformed_fixture_with_exit_code_2(tmp_path, starter_raw, capsys):
    del starter_raw["cases"][3]["metadata"]["event_date"]
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(starter_raw), encoding="utf-8")
    assert main(["evaluate", "--fixture", str(path)]) == 2
    err = capsys.readouterr().err
    assert "invalid input" in err and "cases.3.metadata.event_date: Field required" in err


@pytest.mark.parametrize("content, problem", [
    (b'{"schema_version": "1.0", "x": "\xff"}', "not valid UTF-8"),
    (b"[" * 200000, "nested too deeply"),
    (b'{"schema_version": "1.0", "schema_version": "1.0"}', "duplicate JSON key 'schema_version'"),
    (b'{"x": ' + b"1" * 5000 + b"}", "JSON cannot be parsed"),
])
def test_undecodable_input_is_a_validation_failure_with_exit_code_2(tmp_path, capsys, content, problem):
    path = tmp_path / "bad.json"
    path.write_bytes(content)
    with pytest.raises(InputValidationError, match=problem):
        load_fixture(path)
    assert main(["evaluate", "--fixture", str(path)]) == 2
    assert problem in capsys.readouterr().err


def test_duplicate_key_cannot_silently_flip_a_flag(tmp_path, starter_raw):
    text = json.dumps(starter_raw).replace('"superseded": true', '"superseded": true, "superseded": false', 1)
    path = tmp_path / "dup.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(InputValidationError, match="duplicate JSON key 'superseded'"):
        load_fixture(path)


def test_cli_reports_duplicate_ids_across_sensitivity_fixtures_with_exit_code_2(capsys):
    assert main(["sensitivity", "--fixture", str(WEIGHTING_FIXTURE), "--fixture", str(WEIGHTING_FIXTURE)]) == 2
    assert "appears in more than one fixture" in capsys.readouterr().err
