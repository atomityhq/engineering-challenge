import copy
import datetime as dt
import json

import pytest

from g2_gate.evaluator import evaluate_case
from g2_gate.loading import load_fixture, load_policy, load_weight_sets
from g2_gate.models import EvaluationContext, G2Case
from g2_gate.paths import EDGE_FIXTURE, STARTER_FIXTURE, WEIGHTING_FIXTURE

# A clean, eligible news case (same shape as the starter fixture's current-news).
BASE_METADATA = {
    "source_type": "primary_authority",
    "content_type": "news",
    "published_at": "2026-10-04",
    "event_date": "2026-10-03",
    "effective_from": None,
    "last_verified_at": "2026-10-06",
    "current_status": "current",
    "supported": True,
    "superseded": False,
    "contradiction": False,
    "competitor_product_claim": False,
}


@pytest.fixture(scope="session")
def policy():
    return load_policy()


@pytest.fixture(scope="session")
def weight_sets():
    return load_weight_sets()


@pytest.fixture(scope="session")
def weights(weight_sets):
    return weight_sets.get()


@pytest.fixture(scope="session")
def starter():
    return load_fixture(STARTER_FIXTURE)


@pytest.fixture(scope="session")
def edge_fixture():
    return load_fixture(EDGE_FIXTURE)


@pytest.fixture(scope="session")
def weighting_fixture():
    return load_fixture(WEIGHTING_FIXTURE)


@pytest.fixture
def starter_raw():
    """A fresh, mutable copy of the supplied fixture's JSON."""
    return copy.deepcopy(json.loads(STARTER_FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture(scope="session")
def context(starter):
    return EvaluationContext.from_fixture(starter)


@pytest.fixture
def make_case():
    def _make(case_id="synthetic-case", statement="Synthetic test statement.", **overrides):
        return G2Case.model_validate({"id": case_id, "statement": statement, "metadata": {**BASE_METADATA, **overrides}})
    return _make


@pytest.fixture
def evaluate(context, policy, weights):
    def _run(case, as_of=None, policy_override=None, weights_override=None):
        ctx = context if as_of is None else context.model_copy(update={"as_of": dt.date.fromisoformat(as_of)})
        return evaluate_case(case, ctx, policy_override or policy, weights_override or weights)
    return _run
