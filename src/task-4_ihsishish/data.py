from typing import Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field


Decision = Literal["revise", "human_review"]


class EvaluationResult(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_min_length=1,
        extra="forbid",
    )

    decision: Decision
    reason: str


class InputData(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_min_length=1,
        extra="forbid",
    )

    content_id: str
    text: str
    revised_text: str
    second_revised_text: str | None = None
    evaluation_mode: Literal["manual", "scripted"] | None = None
    evaluation_responses: list[EvaluationResult] | None = Field(
        default=None,
        min_length=1,
    )


class WorkflowState(TypedDict):
    run_id: str
    content_id: str
    text: str
    revised_text: str
    second_revised_text: NotRequired[str | None]
    evaluation_result: Decision | None
    evaluation_reason: str | None
    revision_count: int
    max_revisions: int
    status: str
    events: list[dict[str, str | int]]