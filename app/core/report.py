
from datetime import datetime

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
from app.core.workflow import DebuggingState


class FinalDebuggingReport(BaseModel):
    """Structured, user-facing result from a debugging run."""

    run_id: str = Field(min_length=1)
    created_at: datetime

    issue: IssueRequest
    analysis: IssueAnalysis | None = None
    root_cause: RootCauseAnalysis | None = None

    evidence: list[Evidence] = Field(default_factory=list)

    proposed_fix: ProposedFix | None = None
    validation: ValidationResult | None = None

    validation_attempts: int = Field(default=0, ge=0)

    stage_traces: list[StageTrace] = Field(default_factory=list)
    errors: list[WorkflowError] = Field(default_factory=list)

    status: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ReportBuilder:
    """Build reports from completed or failed workflow states."""

    def build(
        self,
        state: DebuggingState,
    ) -> FinalDebuggingReport:
        """Build a report when all required results are available."""

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

        return self._build_report(
            state,
            status=status,
            message=message,
        )

    def build_failure(
        self,
        state: DebuggingState,
    ) -> FinalDebuggingReport:
        """Build a failure report even when workflow data is incomplete."""

        if state.errors:
            error = state.errors[-1]
            message = (
                f"Debugging workflow failed during '{error.stage}' "
                f"({error.error_type}): {error.message}"
            )
        else:
            message = (
                "Debugging workflow failed before completion. "
                "No detailed workflow error was recorded."
            )

        return self._build_report(
            state,
            status="failed",
            message=message,
        )

    @staticmethod
    def _build_report(
        state: DebuggingState,
        *,
        status: str,
        message: str,
    ) -> FinalDebuggingReport:
        """Copy available workflow data into the final report."""

        return FinalDebuggingReport(
            run_id=state.run_id,
            created_at=state.created_at,
            issue=state.issue,
            analysis=state.analysis,
            root_cause=state.root_cause,
            evidence=state.evidence,
            proposed_fix=state.proposed_fix,
            validation=state.validation,
            validation_attempts=state.validation_attempts,
            stage_traces=state.stage_traces,
            errors=state.errors,
            status=status,
            message=message,
        )