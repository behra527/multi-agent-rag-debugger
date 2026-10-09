from pydantic import BaseModel, Field

from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssueRequest,
    ProposedFix,
    RootCauseAnalysis,
    ValidationResult,
)
from app.core.workflow import DebuggingState


class FinalDebuggingReport(BaseModel):
    """Clean user-facing result produced from workflow state."""

    issue: IssueRequest
    analysis: IssueAnalysis
    root_cause: RootCauseAnalysis
    evidence: list[Evidence] = Field(
        default_factory=list
    )
    proposed_fix: ProposedFix
    validation: ValidationResult

    status: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ReportBuilder:
    """Builds a final debugging report from completed workflow state."""

    def build(
        self,
        state: DebuggingState,
    ) -> FinalDebuggingReport:
        if state.analysis is None:
            raise ValueError(
                "Cannot build report without issue analysis."
            )

        if state.root_cause is None:
            raise ValueError(
                "Cannot build report without root-cause analysis."
            )

        if state.proposed_fix is None:
            raise ValueError(
                "Cannot build report without a proposed fix."
            )

        if state.validation is None:
            raise ValueError(
                "Cannot build report without validation results."
            )

        if state.validation.passed:
            status = "validated"
            message = (
                "The proposed fix was applied in an isolated "
                "workspace and passed validation."
            )
        else:
            status = "failed"
            message = (
                "The proposed fix could not be successfully "
                "validated."
            )

        return FinalDebuggingReport(
            issue=state.issue,
            analysis=state.analysis,
            root_cause=state.root_cause,
            evidence=state.evidence,
            proposed_fix=state.proposed_fix,
            validation=state.validation,
            status=status,
            message=message,
        )