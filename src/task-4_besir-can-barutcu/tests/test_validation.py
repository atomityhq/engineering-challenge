"""Malformed input must fail with a predictable ValidationError before any workflow runs."""

import pytest
from pydantic import ValidationError

from workflow.models import (
    ContentItem,
    FixtureNotFoundError,
    Scenario,
    ScenarioFile,
    check_run_inputs,
    load_content,
    load_scenario,
    load_scenarios,
)

GOOD_ITEM = {"content_id": "content-x", "title": "A title", "body": "A body."}


def error_fields(exc: ValidationError) -> set[str]:
    return {str(err["loc"][0]) for err in exc.errors() if err["loc"]}


# --- content items ---------------------------------------------------------


def test_normal_content_loads():
    item = load_content("content-001")
    assert item.content_id == "content-001"
    assert item.body.startswith("Moving every workload")


def test_content_without_body_is_rejected():
    with pytest.raises(ValidationError) as exc:
        load_content("content-bad")
    assert error_fields(exc.value) == {"body"}


def test_injection_content_is_ordinary_data():
    item = load_content("content-injection")
    assert item.body.startswith("Ignore the rules")


def test_unknown_content_id_is_reported():
    with pytest.raises(FixtureNotFoundError):
        load_content("content-999")


@pytest.mark.parametrize("field", ["content_id", "title", "body"])
def test_whitespace_only_field_is_rejected(field):
    with pytest.raises(ValidationError) as exc:
        ContentItem.model_validate({**GOOD_ITEM, field: "   "})
    assert error_fields(exc.value) == {field}


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError) as exc:
        ContentItem.model_validate({**GOOD_ITEM, "author": "demo"})
    assert error_fields(exc.value) == {"author"}


def test_wrong_type_is_rejected():
    with pytest.raises(ValidationError) as exc:
        ContentItem.model_validate({**GOOD_ITEM, "title": 123})
    assert error_fields(exc.value) == {"title"}


# --- scenarios -------------------------------------------------------------


def test_all_scenarios_load():
    ids = [s.id for s in load_scenarios().scenarios]
    assert ids == ["normal-pass", "one-revision", "revision-limit"]


def test_unknown_scenario_id_is_reported():
    with pytest.raises(FixtureNotFoundError):
        load_scenario("no-such-scenario")


def test_unknown_decision_is_rejected():
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            {"id": "s", "responses": [{"decision": "banana", "reason": "x"}]}
        )


def test_empty_reason_is_rejected():
    with pytest.raises(ValidationError):
        Scenario.model_validate(
            {"id": "s", "responses": [{"decision": "human_review", "reason": " "}]}
        )


def test_scenario_without_responses_is_rejected():
    with pytest.raises(ValidationError):
        Scenario.model_validate({"id": "s", "responses": []})


def test_empty_revised_text_is_rejected():
    with pytest.raises(ValidationError, match="revised_content\\[0\\] is empty"):
        Scenario.model_validate(
            {
                "id": "s",
                "responses": [{"decision": "revise", "reason": "x"}],
                "revised_content": ["  "],
            }
        )


def test_repeated_revised_text_is_rejected():
    with pytest.raises(ValidationError, match="same as revised_content\\[0\\]"):
        Scenario.model_validate(
            {
                "id": "s",
                "responses": [{"decision": "revise", "reason": "x"}] * 2,
                "revised_content": ["Version two.", "Version two."],
            }
        )


def test_duplicate_scenario_ids_are_rejected():
    scenario = {"id": "same", "responses": [{"decision": "human_review", "reason": "x"}]}
    with pytest.raises(ValidationError, match="duplicate scenario ids"):
        ScenarioFile.model_validate(
            {"schema_version": "1.0", "synthetic": True, "scenarios": [scenario, scenario]}
        )


# --- content + scenario together ------------------------------------------


@pytest.mark.parametrize("scenario_id", ["normal-pass", "one-revision", "revision-limit"])
def test_fixture_pairs_are_consistent(scenario_id):
    check_run_inputs(load_content("content-001"), load_scenario(scenario_id))


def test_first_revision_must_change_the_body():
    item = ContentItem.model_validate(GOOD_ITEM)
    scenario = Scenario.model_validate(
        {
            "id": "s",
            "responses": [{"decision": "revise", "reason": "x"}],
            "revised_content": [GOOD_ITEM["body"]],
        }
    )
    with pytest.raises(ValueError, match="same as the original body"):
        check_run_inputs(item, scenario)


def test_missing_revised_text_is_rejected():
    item = ContentItem.model_validate(GOOD_ITEM)
    scenario = Scenario.model_validate(
        {"id": "s", "responses": [{"decision": "revise", "reason": "x"}] * 3, "revised_content": ["One."]}
    )
    with pytest.raises(ValueError, match="needs 2 revised text"):
        check_run_inputs(item, scenario)


def test_lower_revision_limit_needs_fewer_texts():
    check_run_inputs(load_content("content-001"), load_scenario("revision-limit"), max_revisions=1)
