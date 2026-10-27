
from dataclasses import dataclass


MAX_REVISIONS = 2


@dataclass(frozen=True, slots=True)
class RevisionPolicy:
    """Domain policy enforcing the maximum revision attempts."""

    max_revisions: int = MAX_REVISIONS

    def __post_init__(self) -> None:
        if type(self.max_revisions) is not int or self.max_revisions < 0:
            raise ValueError("max_revisions must be a non-negative integer")

    def can_revise(self, revision_count: int) -> bool:
        self._validate_count(revision_count)
        return revision_count < self.max_revisions

    def has_reached_limit(self, revision_count: int) -> bool:
        self._validate_count(revision_count)
        return revision_count >= self.max_revisions

    @staticmethod
    def _validate_count(revision_count: int) -> None:
        if type(revision_count) is not int or revision_count < 0:
            raise ValueError(
                "revision_count must be a non-negative integer"
            )
