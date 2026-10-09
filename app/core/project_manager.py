from app.core.debugging_workflow import DebuggingWorkflow
from app.core.models import IssueRequest
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

    def handle_issue(
        self,
        issue: IssueRequest,
        *,
        top_k: int = 5,
        validation_command: list[str] | None = None,
        max_steps: int = 10,
    ) -> FinalDebuggingReport:
        """Process an issue and return the final debugging report."""

        state = DebuggingState(
            issue=issue
        )

        completed_state = self.workflow.run(
            state,
            top_k=top_k,
            validation_command=validation_command,
            max_steps=max_steps,
        )

        return self.report_builder.build(
            completed_state
        )