from enum import Enum

from app.core.workflow import DebuggingState


class WorkflowStage(str, Enum):
    """Stages that the debugging supervisor can select."""

    ANALYZE = "analyze"
    RETRIEVE = "retrieve"
    ROOT_CAUSE = "root_cause"
    GENERATE_FIX = "generate_fix"
    VALIDATE = "validate"
    COMPLETE = "complete"
    FAILED = "failed"


class Supervisor:
    """Controls which stage should execute next."""

    def decide(
        self,
        state: DebuggingState,
    ) -> WorkflowStage:
        """Select the next workflow stage."""

        if state.analysis is None:
            return WorkflowStage.ANALYZE

        if not state.evidence:
            return WorkflowStage.RETRIEVE

        if state.root_cause is None:
            return WorkflowStage.ROOT_CAUSE

        if state.proposed_fix is None:
            return WorkflowStage.GENERATE_FIX

        if state.validation is None:
            return WorkflowStage.VALIDATE

        if state.validation.passed:
            return WorkflowStage.COMPLETE

        if (
            state.validation_attempts
            < state.max_validation_attempts
        ):
            state.validation = None
            state.proposed_fix = None

            return WorkflowStage.GENERATE_FIX

        return WorkflowStage.FAILED