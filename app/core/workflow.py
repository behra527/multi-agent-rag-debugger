
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
    StageTrace,
    ValidationResult,
    WorkflowError,
)


class DebuggingState(BaseModel):
    """Shared state passed through the debugging workflow."""

    run_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    issue: IssueRequest

    analysis: IssueAnalysis | None = None

    evidence: list[Evidence] = Field(
        default_factory=list
    )

    root_cause: RootCauseAnalysis | None = None

    proposed_fix: ProposedFix | None = None

    validation: ValidationResult | None = None

    validation_attempts: int = 0

    max_validation_attempts: int = Field(
        default=2,
        gt=0,
    )

    stage_traces: list[StageTrace] = Field(
        default_factory=list
    )

    errors: list[WorkflowError] = Field(
        default_factory=list
    )