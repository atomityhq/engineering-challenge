
from workflow.models import ContentItem, EvaluationResult


def evaluate_content(content: ContentItem) -> EvaluationResult:
    """
    Simulates a deterministic content evaluator.

    The markers are used only for local testing.
    """

    body = content.body.upper()

    if "[HUMAN_REVIEW]" in body:
        return EvaluationResult(
            decision="human_review",
            feedback="The content requires human approval.",
            score=0.8,
        )

    if "[REVISE]" in body:
        return EvaluationResult(
            decision="revise",
            feedback="The content needs improvement.",
            score=0.5,
        )

    if "[ALWAYS_REVISE]" in body:
        return EvaluationResult(
        decision="revise",
        feedback="The content still needs improvement.",
        score=0.3,
    )

    return EvaluationResult(
        decision="pass",
        feedback="The content meets the evaluation criteria.",
        score=1.0,
    )

    

def revise_content(content: ContentItem) -> ContentItem:
    """
    Simulates a deterministic content revision.
    """

    revised_body = content.body.replace("[REVISE]", "").strip()

    revised_body += "\n\n[Improved version]"

    return content.model_copy(
        update={"body": revised_body}
    )