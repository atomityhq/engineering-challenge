
import pytest

from workflow.policies import RevisionPolicy


@pytest.fixture
def policy() -> RevisionPolicy:
    return RevisionPolicy()


@pytest.mark.parametrize(
    ("revision_count", "expected"),
    [
        (0, True),
        (1, True),
        (2, False),
        (3, False),
    ],
)
def test_can_revise(policy, revision_count, expected):
    assert policy.can_revise(revision_count) is expected


@pytest.mark.parametrize(
    ("revision_count", "expected"),
    [
        (0, False),
        (1, False),
        (2, True),
        (3, True),
    ],
)
def test_has_reached_limit(policy, revision_count, expected):
    assert policy.has_reached_limit(revision_count) is expected


@pytest.mark.parametrize(
    "invalid_count",
    [-1, True, 1.5, "1", None],
)
def test_reject_invalid_revision_count(policy, invalid_count):
    with pytest.raises(ValueError):
        policy.can_revise(invalid_count)


@pytest.mark.parametrize(
    "invalid_limit",
    [-1, True, 1.5, "2", None],
)
def test_reject_invalid_policy_configuration(invalid_limit):
    with pytest.raises(ValueError):
        RevisionPolicy(max_revisions=invalid_limit)


def test_custom_revision_limit():
    policy = RevisionPolicy(max_revisions=1)

    assert policy.can_revise(0) is True
    assert policy.can_revise(1) is False


def test_default_revision_limit():
    assert RevisionPolicy().max_revisions == 2