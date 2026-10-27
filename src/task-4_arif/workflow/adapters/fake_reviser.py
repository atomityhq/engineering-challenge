
from workflow.models.content import ContentItem
from workflow.models.evaluation import EvaluationResult


class FakeReviser:
    """Deterministic content revision adapter."""

    def revise(
        self,
        content: ContentItem,
        evaluation: EvaluationResult,
        revision_number: int,
    ) -> ContentItem:
        if type(revision_number) is not int or revision_number < 1:
            raise ValueError(
                "revision_number must be a positive integer"
            )

        return content.model_copy(
            update={
                "body": (
                    f"{content.body}\n\n"
                    f"[Revision {revision_number}: "
                    f"{evaluation.reason}]"
                )
            }
        )
