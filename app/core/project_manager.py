
import re

from app.core.debugging_workflow import DebuggingWorkflow
from app.core.models import IssueRequest, WorkflowError
from app.core.report import FinalDebuggingReport, ReportBuilder
from app.core.workflow import DebuggingState


class ProjectManager:
    """Top-level entry point for the debugging system."""

    def __init__(
        self,
        workflow: DebuggingWorkflow,
        report_builder: ReportBuilder | None = None,
    ) -> None:
        self.workflow = workflow
        self.report_builder = report_builder or ReportBuilder()

    @staticmethod
    def _normalize_error_message(message: str) -> str:
        """Normalize whitespace and case for duplicate detection."""
        return re.sub(r"\s+", "", message).casefold()

    def handle_issue(
        self,
        issue: IssueRequest,
        *,
        top_k: int = 5,
        validation_command: list[str] | None = None,
        max_steps: int = 10,
    ) -> FinalDebuggingReport:
        """Run the debugging workflow and return a structured report."""

        state = DebuggingState(issue=issue)

        try:
            completed_state = self.workflow.run(
                state,
                top_k=top_k,
                validation_command=validation_command,
                max_steps=max_steps,
            )

        except Exception as exc:
            error_message = str(exc) or type(exc).__name__
            normalized_message = self._normalize_error_message(
                error_message
            )

            # Do not duplicate an error already recorded by the workflow.
            error_already_recorded = any(
                self._normalize_error_message(error.message)
                == normalized_message
                for error in state.errors
            )

            if not error_already_recorded:
                state.errors.append(
                    WorkflowError(
                        stage="workflow",
                        error_type=type(exc).__name__,
                        message=error_message,
                    )
                )

            return self.report_builder.build_failure(state)

        # Handle a workflow that returns after recording a max-step error.
        if any(
            error.error_type == "MaxStepsExceeded"
            for error in completed_state.errors
        ):
            return self.report_builder.build_failure(completed_state)

        return self.report_builder.build(completed_state)