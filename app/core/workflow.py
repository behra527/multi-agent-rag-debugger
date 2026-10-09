from pydantic import BaseModel, Field

from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
    ValidationResult,
)


class DebuggingState(BaseModel):
    """Shared state passed through the debugging workflow."""

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