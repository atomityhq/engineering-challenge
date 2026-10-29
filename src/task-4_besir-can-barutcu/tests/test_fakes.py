"""The scripted fakes are deterministic and fail loudly when the script runs out."""

import pytest

from workflow.fakes import (
    Evaluator,
    Reviser,
    ScriptedEvaluator,
    ScriptedReviser,
    ScriptExhaustedError,
)
from workflow.models import load_content, load_scenario


@pytest.fixture
def item():
    return load_content("content-001")


@pytest.fixture
def one_revision():
    return load_scenario("one-revision")


# --- interfaces ------------------------------------------------------------


@pytest.mark.parametrize("abstract", [Evaluator, Reviser])
def test_interfaces_cannot_be_used_directly(abstract):
    with pytest.raises(TypeError):
        abstract()


def test_fakes_implement_the_interfaces(one_revision):
    assert isinstance(ScriptedEvaluator(one_revision), Evaluator)
    assert isinstance(ScriptedReviser(one_revision), Reviser)


# --- evaluator -------------------------------------------------------------


def test_evaluator_answers_by_step(item, one_revision):
    evaluator = ScriptedEvaluator(one_revision)
    assert evaluator.evaluate(item, 0).decision == "revise"
    assert evaluator.evaluate(item, 1).decision == "human_review"


def test_evaluator_gives_same_answer_for_same_step(item, one_revision):
    evaluator = ScriptedEvaluator(one_revision)
    first = evaluator.evaluate(item, 1)
    evaluator.evaluate(item, 0)
    assert evaluator.evaluate(item, 1) == first


def test_new_evaluator_gives_same_answers(item, one_revision):
    """A restarted process builds a new fake; the answers must not change."""
    before = ScriptedEvaluator(one_revision).evaluate(item, 1)
    after = ScriptedEvaluator(load_scenario("one-revision")).evaluate(item, 1)
    assert before == after


def test_evaluator_ignores_instructions_in_content():
    item = load_content("content-injection")
    result = ScriptedEvaluator(load_scenario("one-revision")).evaluate(item, 0)
    assert result.decision == "revise"


@pytest.mark.parametrize("step", [2, 10, -1])
def test_evaluator_fails_when_script_runs_out(item, one_revision, step):
    with pytest.raises(ScriptExhaustedError, match="no evaluator response"):
        ScriptedEvaluator(one_revision).evaluate(item, step)


def test_returned_answer_cannot_change_the_script(item, one_revision):
    evaluator = ScriptedEvaluator(one_revision)
    evaluator.evaluate(item, 0).reason = "changed"
    assert evaluator.evaluate(item, 0).reason != "changed"


# --- reviser ---------------------------------------------------------------


def test_reviser_uses_text_for_step(item):
    scenario = load_scenario("revision-limit")
    reviser = ScriptedReviser(scenario)
    assert reviser.revise(item, 0).body == scenario.revised_content[0]
    assert reviser.revise(item, 1).body == scenario.revised_content[1]


def test_reviser_keeps_id_and_title(item, one_revision):
    revised = ScriptedReviser(one_revision).revise(item, 0)
    assert revised.content_id == item.content_id
    assert revised.title == item.title
    assert revised.body != item.body


def test_reviser_does_not_change_the_original(item, one_revision):
    original_body = item.body
    ScriptedReviser(one_revision).revise(item, 0)
    assert item.body == original_body


@pytest.mark.parametrize("scenario_id, step", [("normal-pass", 0), ("one-revision", 1), ("revision-limit", 2)])
def test_reviser_fails_when_no_text_left(item, scenario_id, step):
    with pytest.raises(ScriptExhaustedError, match="no revised text"):
        ScriptedReviser(load_scenario(scenario_id)).revise(item, step)
