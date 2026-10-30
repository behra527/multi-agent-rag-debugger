from __future__ import annotations

from enum import Enum


class RepairState(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    INVESTIGATING = "INVESTIGATING"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    FIX_PROPOSED = "FIX_PROPOSED"
    PRE_APPROVAL_CHECKS = "PRE_APPROVAL_CHECKS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    APPLYING_TO_CANDIDATE = "APPLYING_TO_CANDIDATE"
    TESTING = "TESTING"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    REPAIR_ANALYSIS = "REPAIR_ANALYSIS"
    FIX_REVISION = "FIX_REVISION"
    READY_FOR_INTEGRATION = "READY_FOR_INTEGRATION"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


LEGAL_TRANSITIONS: dict[RepairState, frozenset[RepairState]] = {
    RepairState.RECEIVED: frozenset({RepairState.VALIDATING, RepairState.CANCELLED, RepairState.BLOCKED}),
    RepairState.VALIDATING: frozenset({RepairState.INVESTIGATING, RepairState.BLOCKED, RepairState.CANCELLED}),
    RepairState.INVESTIGATING: frozenset(
        {RepairState.ROOT_CAUSE_IDENTIFIED, RepairState.BLOCKED, RepairState.CANCELLED}
    ),
    RepairState.ROOT_CAUSE_IDENTIFIED: frozenset(
        {RepairState.FIX_PROPOSED, RepairState.BLOCKED, RepairState.CANCELLED}
    ),
    RepairState.FIX_PROPOSED: frozenset(
        {RepairState.PRE_APPROVAL_CHECKS, RepairState.BLOCKED, RepairState.CANCELLED}
    ),
    RepairState.PRE_APPROVAL_CHECKS: frozenset(
        {RepairState.AWAITING_APPROVAL, RepairState.BLOCKED, RepairState.CANCELLED}
    ),
    RepairState.AWAITING_APPROVAL: frozenset(
        {
            RepairState.APPROVED,
            RepairState.REJECTED,
            RepairState.CANCELLED,
            RepairState.REPAIR_ANALYSIS,
        }
    ),
    RepairState.APPROVED: frozenset({RepairState.APPLYING_TO_CANDIDATE, RepairState.CANCELLED}),
    RepairState.APPLYING_TO_CANDIDATE: frozenset({RepairState.TESTING, RepairState.BLOCKED}),
    RepairState.TESTING: frozenset(
        {RepairState.READY_FOR_INTEGRATION, RepairState.VERIFICATION_FAILED, RepairState.BLOCKED}
    ),
    RepairState.VERIFICATION_FAILED: frozenset(
        {RepairState.REPAIR_ANALYSIS, RepairState.BLOCKED, RepairState.CANCELLED}
    ),
    RepairState.REPAIR_ANALYSIS: frozenset({RepairState.FIX_REVISION, RepairState.BLOCKED}),
    RepairState.FIX_REVISION: frozenset({RepairState.PRE_APPROVAL_CHECKS, RepairState.BLOCKED}),
    RepairState.READY_FOR_INTEGRATION: frozenset(
        {RepairState.COMPLETED, RepairState.CANCELLED, RepairState.AWAITING_APPROVAL}
    ),
    RepairState.BLOCKED: frozenset({RepairState.CANCELLED, RepairState.AWAITING_APPROVAL}),
    RepairState.COMPLETED: frozenset(),
    RepairState.REJECTED: frozenset(),
    RepairState.CANCELLED: frozenset(),
}


class IllegalTransition(ValueError):
    """Raised when a workflow transition is not allowed."""


def transition(current: RepairState, target: RepairState) -> RepairState:
    allowed = LEGAL_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise IllegalTransition(f"Cannot move from {current.value} to {target.value}.")
    return target
