import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.models import (
    Evidence,
    IssueAnalysis,
    IssuePriority,
    IssueRequest,
    IssueType,
    ProposedFix,
    RootCauseAnalysis,
    StageTrace,
    ValidationResult,
)
from app.core.report import FinalDebuggingReport
from app.db.models import (
    ApprovalRecord,
    DebuggingRunRecord,
    EvidenceRecord,
    IssueRecord,
    ProposedFixRecord,
    RepositoryRecord,
    RootCauseRecord,
    StageTraceRecord,
    ValidationRecord,
)


class PersistenceService:
    """Handles database persistence and queries for debugging sessions."""

    @staticmethod
    def save_report(report: FinalDebuggingReport, db: Session) -> DebuggingRunRecord:
        """Persist or update a complete debugging run and its artifacts."""
        run = db.get(DebuggingRunRecord, report.run_id)

        duration = None
        if report.stage_traces:
            duration = sum(t.duration_ms or 0 for t in report.stage_traces)

        if not run:
            run = DebuggingRunRecord(
                id=report.run_id,
                created_at=report.created_at,
                status=report.status,
                title=report.issue.title,
                description=report.issue.description,
                repository_path=report.issue.repository_path,
                duration_ms=duration,
                message=report.message,
                approval_status="pending",
            )
            db.add(run)
        else:
            run.status = report.status
            run.duration_ms = duration
            run.message = report.message

        # Persist Issue Analysis
        if report.analysis:
            if run.analysis:
                db.delete(run.analysis)
            run.analysis = IssueRecord(
                run_id=run.id,
                issue_type=report.analysis.issue_type.value,
                priority=report.analysis.priority.value,
                summary=report.analysis.summary,
                affected_components_json=json.dumps(report.analysis.affected_components),
                search_queries_json=json.dumps(report.analysis.search_queries),
            )

        # Persist Root Cause Analysis
        if report.root_cause:
            if run.root_cause:
                db.delete(run.root_cause)
            run.root_cause = RootCauseRecord(
                run_id=run.id,
                root_cause=report.root_cause.root_cause,
                explanation=report.root_cause.explanation,
                affected_files_json=json.dumps(report.root_cause.affected_files),
                evidence_json=json.dumps(report.root_cause.evidence),
                confidence=report.root_cause.confidence,
            )

        # Persist Proposed Fix
        if report.proposed_fix:
            if run.proposed_fix:
                db.delete(run.proposed_fix)
            run.proposed_fix = ProposedFixRecord(
                run_id=run.id,
                summary=report.proposed_fix.summary,
                affected_files_json=json.dumps(report.proposed_fix.affected_files),
                patch=report.proposed_fix.patch,
                reasoning=report.proposed_fix.reasoning,
            )

        # Persist Validation Result
        if report.validation:
            if run.validation:
                db.delete(run.validation)
            run.validation = ValidationRecord(
                run_id=run.id,
                passed=report.validation.passed,
                tests_run=report.validation.tests_run,
                tests_passed=report.validation.tests_passed,
                tests_failed=report.validation.tests_failed,
                output=report.validation.output,
                errors_json=json.dumps(report.validation.errors),
                attempts=report.validation_attempts,
            )

        # Persist Evidence
        if report.evidence:
            for item in list(run.evidence_items):
                db.delete(item)
            for ev in report.evidence:
                run.evidence_items.append(
                    EvidenceRecord(
                        run_id=run.id,
                        source=ev.source,
                        content=ev.content,
                        score=ev.score,
                        start_line=ev.start_line,
                        end_line=ev.end_line,
                        language=ev.language,
                        symbols_json=json.dumps(getattr(ev, "symbols", [])),
                    )
                )

        # Persist Stage Traces
        if report.stage_traces:
            for trace_rec in list(run.stage_traces):
                db.delete(trace_rec)
            for st in report.stage_traces:
                run.stage_traces.append(
                    StageTraceRecord(
                        run_id=run.id,
                        stage=st.stage,
                        status=st.status,
                        started_at=st.started_at,
                        finished_at=st.finished_at,
                        duration_ms=st.duration_ms,
                        error_type=st.error_type,
                        error_message=st.error_message,
                    )
                )

        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_run(run_id: str, db: Session) -> DebuggingRunRecord | None:
        """Fetch a specific debugging run with relationships."""
        return db.get(DebuggingRunRecord, run_id)

    @staticmethod
    def list_runs(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        search: str | None = None,
    ) -> list[DebuggingRunRecord]:
        """List historical runs with optional status filtering and query search."""
        query = select(DebuggingRunRecord).order_by(desc(DebuggingRunRecord.created_at))

        if status:
            query = query.where(DebuggingRunRecord.status == status)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (DebuggingRunRecord.title.ilike(search_pattern))
                | (DebuggingRunRecord.description.ilike(search_pattern))
                | (DebuggingRunRecord.repository_path.ilike(search_pattern))
            )

        return list(db.scalars(query.offset(skip).limit(limit)).all())

    @staticmethod
    def record_approval(
        run_id: str,
        status: str,
        reviewer: str,
        comment: str | None,
        db: Session,
    ) -> ApprovalRecord:
        """Record human approval or rejection of a patch."""
        run = db.get(DebuggingRunRecord, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found.")

        run.approval_status = status

        approval = ApprovalRecord(
            run_id=run_id,
            status=status,
            reviewer=reviewer,
            comment=comment,
            reviewed_at=datetime.now(timezone.utc),
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def get_metrics(db: Session) -> dict[str, Any]:
        """Compute real operational metrics from actual database records."""
        total_runs = db.scalar(select(func.count(DebuggingRunRecord.id))) or 0
        completed_runs = db.scalar(
            select(func.count(DebuggingRunRecord.id)).where(DebuggingRunRecord.status.in_(["completed", "validated"]))
        ) or 0
        failed_runs = db.scalar(
            select(func.count(DebuggingRunRecord.id)).where(DebuggingRunRecord.status == "failed")
        ) or 0
        approved_fixes = db.scalar(
            select(func.count(DebuggingRunRecord.id)).where(DebuggingRunRecord.approval_status == "approved")
        ) or 0
        avg_duration = db.scalar(
            select(func.avg(DebuggingRunRecord.duration_ms)).where(DebuggingRunRecord.duration_ms.isnot(None))
        ) or 0.0

        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "failed_runs": failed_runs,
            "approved_fixes": approved_fixes,
            "success_rate": round((completed_runs / total_runs * 100), 1) if total_runs > 0 else 0.0,
            "avg_duration_ms": round(float(avg_duration), 1),
        }
