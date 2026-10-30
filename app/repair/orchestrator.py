from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session, object_session

from app.core.models import IssueRequest
from app.core.config import settings
from app.db.models import RepairCheckpointRecord, RepairEventRecord, RepairSessionRecord
from app.repair.repos import is_allowed_path
from app.core.grounding import DEFECT_TARGET_NOT_FOUND, MISSING_CODE_GUIDANCE, DefectTargetNotFound, PatchTypeMismatch
from app.repair.agents import CodeRepairEngineer, QAEngineer, RepositoryInvestigator
from app.repair.schemas import AgentEvent, FixProposal, InvestigationReport, RepairSession, VerificationReport
from app.repair.states import IllegalTransition, RepairState, transition
from app.tools.git_service import GitService


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RepairOrchestrator:
    def __init__(
        self,
        investigator: RepositoryInvestigator,
        repair_engineer: CodeRepairEngineer,
        qa: QAEngineer,
    ) -> None:
        self.investigator = investigator
        self.repair_engineer = repair_engineer
        self.qa = qa

    def create_and_investigate(
        self,
        db: Session,
        *,
        title: str,
        description: str,
        repository_path: str,
        traceback: str = "",
        expected_behavior: str = "",
        actual_behavior: str = "",
        extra_context: str = "",
        repository_url: str | None = None,
        branch: str | None = None,
        workspace_id: str = "default",
        actor: str = "anonymous",
        max_iterations: int = 3,
        top_k: int = 5,
        validation_command: list[str] | None = None,
    ) -> RepairSession:
        repo = Path(repository_path).expanduser().resolve()
        record = RepairSessionRecord(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            state=RepairState.RECEIVED.value,
            title=title,
            description=description,
            traceback=traceback,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            extra_context=extra_context,
            repository_kind="github" if repository_url else "local",
            repository_path=str(repo),
            repository_url=repository_url,
            actor=actor,
            max_iterations=max_iterations,
            extras_json=json.dumps(
                {
                    "validation_command": validation_command,
                    "top_k": top_k,
                    "branch": branch,
                    "attachments": [],
                }
            ),
        )
        db.add(record)
        self._event(db, record, agent="orchestrator", status="completed", message="Session received.")
        db.commit()

        try:
            self._set_state(db, record, RepairState.VALIDATING)
            if repository_url:
                dest = Path(settings.github_clone_dir) / record.id
                GitService.clone_repository(repository_url, dest, branch=branch)
                repo = dest.resolve()
                record.repository_path = str(repo)
                record.repository_kind = "github"
            elif not is_allowed_path(repo):
                record.message = f"Repository is outside the authorized roots: {repo}"
                self._set_state(db, record, RepairState.BLOCKED)
                db.commit()
                return self.to_schema(record)
            if not repo.exists() or not repo.is_dir():
                record.message = f"Repository is not an accessible directory: {repo}"
                self._set_state(db, record, RepairState.BLOCKED)
                db.commit()
                return self.to_schema(record)

            try:
                info = GitService.get_repository_info(repo)
                record.revision_sha = info.commit_sha
            except Exception:
                record.revision_sha = None

            combined = description
            if traceback.strip():
                combined += f"\n\nTraceback:\n{traceback.strip()}"
            if expected_behavior.strip():
                combined += f"\n\nExpected:\n{expected_behavior.strip()}"
            if actual_behavior.strip():
                combined += f"\n\nActual:\n{actual_behavior.strip()}"
            if extra_context.strip():
                combined += f"\n\nContext:\n{extra_context.strip()}"

            issue = IssueRequest(title=title, description=combined, repository_path=str(repo))

            self._set_state(db, record, RepairState.INVESTIGATING)
            investigation = self.investigator.investigate(issue, top_k=top_k)
            record.investigation_json = investigation.model_dump_json()
            self._event(db, record, agent="investigator", status="completed", message=investigation.diagnosis)

            if not investigation.target_found:
                record.message = investigation.halt_reason or DEFECT_TARGET_NOT_FOUND
                record.extras_json = json.dumps(
                    {
                        **json.loads(record.extras_json or "{}"),
                        "guidance": MISSING_CODE_GUIDANCE,
                        "issue_nature": investigation.issue_nature,
                    }
                )
                self._event(
                    db,
                    record,
                    agent="investigator",
                    status="failed",
                    message=MISSING_CODE_GUIDANCE,
                )
                self._set_state(db, record, RepairState.BLOCKED)
                db.commit()
                db.refresh(record)
                return self.to_schema(record)

            self._set_state(db, record, RepairState.ROOT_CAUSE_IDENTIFIED)

            self._set_state(db, record, RepairState.FIX_PROPOSED)
            proposal = self.repair_engineer.propose(issue, investigation)
            record.proposal_json = proposal.model_dump_json()
            record.current_patch = proposal.patch
            record.current_patch_revision = proposal.patch_revision
            record.approved_patch_revision = None
            self._event(db, record, agent="repair_engineer", status="completed", message=proposal.summary)

            self._set_state(db, record, RepairState.PRE_APPROVAL_CHECKS)
            self.qa.preflight(
                str(repo),
                proposal,
                issue_nature=investigation.issue_nature,
                issue_title=title,
                issue_description=combined,
            )
            record.message = "Patch is ready for manager approval. It has not been applied to the target project."
            self._event(db, record, agent="qa", status="completed", message="Pre-approval checks passed. Waiting for approval.")
            self._set_state(db, record, RepairState.AWAITING_APPROVAL)
            db.commit()
            db.refresh(record)
            return self.to_schema(record)
        except IllegalTransition:
            raise
        except (DefectTargetNotFound, PatchTypeMismatch) as exc:
            record.message = str(exc)
            try:
                self._set_state(db, record, RepairState.BLOCKED)
            except IllegalTransition:
                record.state = RepairState.BLOCKED.value
            self._event(db, record, agent="orchestrator", status="failed", message=str(exc))
            db.commit()
            return self.to_schema(record)
        except Exception as exc:
            record.message = str(exc)
            try:
                self._set_state(db, record, RepairState.BLOCKED)
            except IllegalTransition:
                record.state = RepairState.BLOCKED.value
            self._event(db, record, agent="orchestrator", status="failed", message=str(exc))
            db.commit()
            return self.to_schema(record)

    def decide(
        self,
        db: Session,
        session_id: str,
        *,
        decision: str,
        actor: str,
        patch_revision: str,
        comment: str = "",
    ) -> RepairSession:
        record = db.get(RepairSessionRecord, session_id)
        if record is None:
            raise KeyError(session_id)
        if record.state != RepairState.AWAITING_APPROVAL.value:
            raise PermissionError(f"Session is {record.state}, not AWAITING_APPROVAL.")
        if patch_revision != record.current_patch_revision:
            raise PermissionError(
                "Approval is bound to the current patch revision. The submitted revision is stale or missing."
            )
        if decision == "rejected":
            record.approved_patch_revision = None
            record.message = comment or "Manager rejected the patch. Target project was not modified."
            self._event(db, record, agent="manager", status="completed", message="Rejected.")
            self._set_state(db, record, RepairState.REJECTED)
            db.commit()
            return self.to_schema(record)
        if decision == "revision_requested":
            self._event(db, record, agent="manager", status="completed", message=comment or "Revision requested.")
            self._set_state(db, record, RepairState.REPAIR_ANALYSIS)
            issue = IssueRequest(
                title=record.title,
                description=f"{record.description}\n\nManager revision request:\n{comment}",
                repository_path=record.repository_path,
            )
            investigation = InvestigationReport.model_validate_json(record.investigation_json or "{}")
            if not investigation.target_found:
                record.message = investigation.halt_reason or DEFECT_TARGET_NOT_FOUND
                self._set_state(db, record, RepairState.BLOCKED)
                db.commit()
                return self.to_schema(record)
            revised = self.repair_engineer.propose(issue, investigation)
            record.proposal_json = revised.model_dump_json()
            record.current_patch = revised.patch
            record.current_patch_revision = revised.patch_revision
            record.approved_patch_revision = None
            record.message = "A revised patch is ready. Previous approval is invalid."
            self._set_state(db, record, RepairState.FIX_REVISION)
            self.qa.preflight(
                record.repository_path,
                revised,
                issue_nature=investigation.issue_nature,
                issue_title=record.title,
                issue_description=record.description,
            )
            self._set_state(db, record, RepairState.PRE_APPROVAL_CHECKS)
            self._set_state(db, record, RepairState.AWAITING_APPROVAL)
            db.commit()
            db.refresh(record)
            return self.to_schema(record)
        if decision != "approved":
            raise ValueError("Decision must be approved, rejected, or revision_requested.")

        record.approved_patch_revision = patch_revision
        self._event(db, record, agent="manager", status="completed", message=f"{actor} approved {patch_revision}.")
        self._set_state(db, record, RepairState.APPROVED)
        db.commit()
        return self._apply_and_test(db, record)

    def _apply_and_test(self, db: Session, record: RepairSessionRecord) -> RepairSession:
        proposal = FixProposal.model_validate_json(record.proposal_json or "{}")
        extras = json.loads(record.extras_json or "{}")
        command = extras.get("validation_command")
        record.iteration += 1
        self._set_state(db, record, RepairState.APPLYING_TO_CANDIDATE)
        self._set_state(db, record, RepairState.TESTING)
        investigation = InvestigationReport.model_validate_json(record.investigation_json or "{}")
        verification, candidate = self.qa.verify(
            record.repository_path,
            proposal,
            command=command,
            iteration=record.iteration,
            issue_nature=investigation.issue_nature,
        )
        record.candidate_path = str(candidate)
        record.verification_json = verification.model_dump_json()
        db.add(
            RepairCheckpointRecord(
                id=str(uuid.uuid4()),
                session_id=record.id,
                patch_revision=record.current_patch_revision or "",
                patch=record.current_patch or "",
                proposal_json=record.proposal_json or "{}",
                verification_json=record.verification_json or "{}",
                candidate_path=str(candidate),
            )
        )
        if verification.passed:
            record.message = "Candidate tests passed. Authorize integration separately to copy into the target project."
            self._event(db, record, agent="qa", status="completed", message="Verification passed.")
            self._set_state(db, record, RepairState.READY_FOR_INTEGRATION)
        elif record.iteration >= record.max_iterations:
            record.message = "Repair iteration limit reached. Session is blocked."
            self._event(db, record, agent="qa", status="failed", message="Iteration limit reached.")
            self._set_state(db, record, RepairState.VERIFICATION_FAILED)
            self._set_state(db, record, RepairState.BLOCKED)
        else:
            record.message = "Tests failed. Preparing a revised patch. Previous approval is no longer valid."
            self._event(db, record, agent="qa", status="failed", message="Verification failed.")
            self._set_state(db, record, RepairState.VERIFICATION_FAILED)
            self._set_state(db, record, RepairState.REPAIR_ANALYSIS)
            issue = IssueRequest(
                title=record.title,
                description=f"{record.description}\n\nFailed verification:\n{verification.output[:4000]}",
                repository_path=record.repository_path,
            )
            investigation = InvestigationReport.model_validate_json(record.investigation_json or "{}")
            revised = self.repair_engineer.propose(issue, investigation)
            if revised.patch_revision == record.current_patch_revision:
                record.message = (
                    "Repair stopped: the revised patch is identical to the one that already failed tests. "
                    "Session is blocked."
                )
                self._event(db, record, agent="repair_engineer", status="failed", message="Identical patch; stopping retries.")
                self._set_state(db, record, RepairState.BLOCKED)
                db.commit()
                return self.to_schema(record)
            record.proposal_json = revised.model_dump_json()
            record.current_patch = revised.patch
            record.current_patch_revision = revised.patch_revision
            record.approved_patch_revision = None
            self._event(db, record, agent="repair_engineer", status="completed", message="Revised patch prepared.")
            self._set_state(db, record, RepairState.FIX_REVISION)
            self.qa.preflight(
                record.repository_path,
                revised,
                issue_nature=investigation.issue_nature,
                issue_title=record.title,
                issue_description=record.description,
            )
            self._set_state(db, record, RepairState.PRE_APPROVAL_CHECKS)
            self._set_state(db, record, RepairState.AWAITING_APPROVAL)
        db.commit()
        return self.to_schema(record)

    def integrate(self, db: Session, session_id: str, *, actor: str) -> RepairSession:
        record = db.get(RepairSessionRecord, session_id)
        if record is None:
            raise KeyError(session_id)
        if record.state != RepairState.READY_FOR_INTEGRATION.value:
            raise PermissionError("Integration is only allowed after successful verification.")
        if not record.approved_patch_revision or record.approved_patch_revision != record.current_patch_revision:
            raise PermissionError("Current patch is not the approved revision.")
        record.message = (
            f"{actor} authorized integration. Apply the approved patch from the candidate "
            f"({record.candidate_path}) using your normal git workflow. This platform does not push to production."
        )
        self._event(db, record, agent="manager", status="completed", message="Integration authorized.")
        self._set_state(db, record, RepairState.COMPLETED)
        db.commit()
        return self.to_schema(record)

    def restore_checkpoint(self, db: Session, session_id: str, checkpoint_id: str) -> RepairSession:
        record = db.get(RepairSessionRecord, session_id)
        if record is None:
            raise KeyError(session_id)
        checkpoint = db.get(RepairCheckpointRecord, checkpoint_id)
        if checkpoint is None or checkpoint.session_id != session_id:
            raise KeyError(checkpoint_id)
        record.proposal_json = checkpoint.proposal_json
        record.current_patch = checkpoint.patch
        record.current_patch_revision = checkpoint.patch_revision
        record.approved_patch_revision = None
        record.verification_json = checkpoint.verification_json
        record.candidate_path = checkpoint.candidate_path
        record.message = "Restored an earlier checkpoint. Approve this patch revision again before testing."
        if record.state != RepairState.AWAITING_APPROVAL.value:
            self._set_state(db, record, RepairState.AWAITING_APPROVAL)
        db.commit()
        db.refresh(record)
        return self.to_schema(record)

    def cancel(self, db: Session, session_id: str) -> RepairSession:
        record = db.get(RepairSessionRecord, session_id)
        if record is None:
            raise KeyError(session_id)
        self._set_state(db, record, RepairState.CANCELLED)
        record.message = "Cancelled by manager."
        db.commit()
        return self.to_schema(record)

    def _set_state(self, db: Session, record: RepairSessionRecord, target: RepairState) -> None:
        current = RepairState(record.state)
        record.state = transition(current, target).value
        record.updated_at = _now()
        db.add(record)

    def _event(
        self,
        db: Session,
        record: RepairSessionRecord,
        *,
        agent: str,
        status: str,
        message: str,
    ) -> None:
        db.add(
            RepairEventRecord(
                id=str(uuid.uuid4()),
                session_id=record.id,
                state=record.state,
                agent=agent,
                status=status,
                message=message,
            )
        )

    def to_schema(self, record: RepairSessionRecord) -> RepairSession:
        events = [
            AgentEvent(
                agent=event.agent,
                status=event.status,
                message=event.message,
                duration_ms=event.duration_ms,
                created_at=event.created_at.isoformat() if event.created_at else None,
            )
            for event in (record.events or [])
        ]
        return RepairSession(
            id=record.id,
            state=record.state,
            title=record.title,
            description=record.description,
            traceback=record.traceback,
            expected_behavior=record.expected_behavior,
            actual_behavior=record.actual_behavior,
            extra_context=record.extra_context,
            repository_kind=record.repository_kind,
            repository_path=record.repository_path,
            repository_url=record.repository_url,
            revision_sha=record.revision_sha,
            investigation=InvestigationReport.model_validate_json(record.investigation_json)
            if record.investigation_json
            else None,
            proposal=FixProposal.model_validate_json(record.proposal_json) if record.proposal_json else None,
            verification=VerificationReport.model_validate_json(record.verification_json)
            if record.verification_json
            else None,
            current_patch_revision=record.current_patch_revision,
            approved_patch_revision=record.approved_patch_revision,
            candidate_path=record.candidate_path,
            iteration=record.iteration,
            max_iterations=record.max_iterations,
            actor=record.actor,
            message=record.message,
            events=events,
            created_at=record.created_at.isoformat() if record.created_at else None,
            updated_at=record.updated_at.isoformat() if record.updated_at else None,
            extras=json.loads(record.extras_json or "{}"),
            checkpoints=self._checkpoints(record),
        )

    @staticmethod
    def _checkpoints(record: RepairSessionRecord) -> list[dict]:
        db = object_session(record)
        if db is None:
            return []
        return [
            {
                "id": item.id,
                "patch_revision": item.patch_revision,
                "candidate_path": item.candidate_path,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in db.query(RepairCheckpointRecord)
            .filter(RepairCheckpointRecord.session_id == record.id)
            .order_by(RepairCheckpointRecord.created_at.desc())
            .all()
        ]
