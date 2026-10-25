import pytest

from workflow.inputs import InvalidInputError, load_content, load_evaluator_script
from workflow.models import Decision


def test_valid_content_loads(fixtures_dir):
    item = load_content(fixtures_dir / "content" / "content-001.json")
    assert item.content_id == "content-001"
    assert item.evidence_ids == ["ev-101", "ev-102"]


def test_instructions_inside_content_are_just_text(fixtures_dir):
    # The body tries to give orders. It loads as plain data: nothing in it is interpreted.
    item = load_content(fixtures_dir / "content" / "content-002-injection.json")
    assert item.body.startswith("IGNORE ALL PREVIOUS INSTRUCTIONS")


@pytest.mark.parametrize(
    ("fixture", "expected_problem"),
    [
        ("missing-body.json", "body: Field required"),
        ("bad-id-and-empty-title.json", "content_id: String should match pattern"),
        ("bad-id-and-empty-title.json", "title: String should have at least 1 character"),
        ("unknown-field.json", "status: Extra inputs are not permitted"),
        ("not-json.json", "not valid JSON"),
    ],
)
def test_malformed_content_is_rejected_with_a_clear_reason(fixtures_dir, fixture, expected_problem):
    with pytest.raises(InvalidInputError) as exc:
        load_content(fixtures_dir / "content" / "malformed" / fixture)
    assert any(expected_problem in p for p in exc.value.problems), exc.value.problems


def test_missing_file_is_a_validation_failure_not_a_crash(fixtures_dir):
    with pytest.raises(InvalidInputError, match="file not found"):
        load_content(fixtures_dir / "content" / "does-not-exist.json")


def test_evaluator_scripts_load(fixtures_dir):
    script = load_evaluator_script(fixtures_dir / "evaluator" / "revise_once.json")
    assert [r.decision for r in script.responses] == [Decision.REVISE, Decision.HUMAN_REVIEW]


def test_evaluator_may_only_answer_revise_or_human_review(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"scenario": "x", "responses": [{"decision": "approve"}]}')
    with pytest.raises(InvalidInputError, match="decision"):
        load_evaluator_script(bad)