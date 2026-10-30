import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RepositoryRecord(Base):
    """Stores metadata for scanned and indexed repositories."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    path: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DebuggingRunRecord(Base):
    """Top-level record tracking a debugging workflow run."""

    __tablename__ = "debugging_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # UUID
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)  # running, completed, failed
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    repository_path: Mapped[str] = mapped_column(String(1024), index=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)  # pending, approved, rejected

    # Child relationships
    analysis: Mapped["IssueRecord | None"] = relationship(
        "IssueRecord", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    root_cause: Mapped["RootCauseRecord | None"] = relationship(
        "RootCauseRecord", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    proposed_fix: Mapped["ProposedFixRecord | None"] = relationship(
        "ProposedFixRecord", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    validation: Mapped["ValidationRecord | None"] = relationship(
        "ValidationRecord", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list["EvidenceRecord"]] = relationship(
        "EvidenceRecord", back_populates="run", cascade="all, delete-orphan"
    )
    stage_traces: Mapped[list["StageTraceRecord"]] = relationship(
        "StageTraceRecord", back_populates="run", cascade="all, delete-orphan"
    )
    approval_history: Mapped[list["ApprovalRecord"]] = relationship(
        "ApprovalRecord", back_populates="run", cascade="all, delete-orphan"
    )


class IssueRecord(Base):
    __tablename__ = "issue_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), unique=True)
    issue_type: Mapped[str] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    affected_components_json: Mapped[str] = mapped_column(Text, default="[]")
    search_queries_json: Mapped[str] = mapped_column(Text, default="[]")

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="analysis")

    @property
    def affected_components(self) -> list[str]:
        return json.loads(self.affected_components_json)

    @property
    def search_queries(self) -> list[str]:
        return json.loads(self.search_queries_json)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), index=True)
    source: Mapped[str] = mapped_column(String(1024))
    content: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(64))
    symbols_json: Mapped[str] = mapped_column(Text, default="[]")

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="evidence_items")


class RootCauseRecord(Base):
    __tablename__ = "root_cause_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), unique=True)
    root_cause: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    affected_files_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float)

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="root_cause")


class ProposedFixRecord(Base):
    __tablename__ = "proposed_fix_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    affected_files_json: Mapped[str] = mapped_column(Text, default="[]")
    patch: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text)

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="proposed_fix")


class ValidationRecord(Base):
    __tablename__ = "validation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), unique=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    tests_run: Mapped[int] = mapped_column(Integer, default=0)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_failed: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[str] = mapped_column(Text, default="")
    errors_json: Mapped[str] = mapped_column(Text, default="[]")
    attempts: Mapped[int] = mapped_column(Integer, default=1)

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="validation")


class StageTraceRecord(Base):
    __tablename__ = "stage_trace_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="stage_traces")


class WorkspaceMixin:
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")


class KnowledgeBaseRecord(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    chunk_size: Mapped[int] = mapped_column(Integer, default=800)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=120)
    embedding_provider: Mapped[str] = mapped_column(String(64), default="local")
    embedding_model: Mapped[str] = mapped_column(String(255), default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=384)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list["DocumentRecord"]] = relationship(
        "DocumentRecord", back_populates="knowledge_base", cascade="all, delete-orphan"
    )


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_base_id: Mapped[str] = mapped_column(String(64), ForeignKey("knowledge_bases.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="text/plain")
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    knowledge_base: Mapped["KnowledgeBaseRecord"] = relationship(
        "KnowledgeBaseRecord", back_populates="documents"
    )


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DebugSessionRecord(Base):
    __tablename__ = "debug_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    knowledge_base_id: Mapped[str] = mapped_column(String(64), ForeignKey("knowledge_bases.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationDatasetRecord(Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list["EvaluationItemRecord"]] = relationship(
        "EvaluationItemRecord", back_populates="dataset", cascade="all, delete-orphan"
    )


class EvaluationItemRecord(Base):
    __tablename__ = "evaluation_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("evaluation_datasets.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevant_document_ids_json: Mapped[str] = mapped_column(Text, default="[]")

    dataset: Mapped["EvaluationDatasetRecord"] = relationship(
        "EvaluationDatasetRecord", back_populates="items"
    )


class ExperimentRecord(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    name: Mapped[str] = mapped_column(String(255))
    knowledge_base_id: Mapped[str] = mapped_column(String(64), ForeignKey("knowledge_bases.id"))
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("evaluation_datasets.id"))
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    results_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("debugging_runs.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))  # approved, rejected, revision_requested
    reviewer: Mapped[str] = mapped_column(String(128), default="developer")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped["DebuggingRunRecord"] = relationship("DebuggingRunRecord", back_populates="approval_history")


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    workspace_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionTokenRecord(Base):
    __tablename__ = "session_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RepairSessionRecord(Base):
    __tablename__ = "repair_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    state: Mapped[str] = mapped_column(String(64), index=True, default="RECEIVED")
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    traceback: Mapped[str] = mapped_column(Text, default="")
    expected_behavior: Mapped[str] = mapped_column(Text, default="")
    actual_behavior: Mapped[str] = mapped_column(Text, default="")
    extra_context: Mapped[str] = mapped_column(Text, default="")
    repository_kind: Mapped[str] = mapped_column(String(32), default="local")
    repository_path: Mapped[str] = mapped_column(String(1024))
    repository_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    revision_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    investigation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposal_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_patch_revision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_patch_revision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    candidate_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    max_iterations: Mapped[int] = mapped_column(Integer, default=3)
    actor: Mapped[str] = mapped_column(String(255), default="anonymous")
    message: Mapped[str] = mapped_column(Text, default="")
    extras_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    events: Mapped[list["RepairEventRecord"]] = relationship(
        "RepairEventRecord", back_populates="session", cascade="all, delete-orphan"
    )


class RepairEventRecord(Base):
    __tablename__ = "repair_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("repair_sessions.id"), index=True)
    state: Mapped[str] = mapped_column(String(64), default="")
    agent: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped["RepairSessionRecord"] = relationship("RepairSessionRecord", back_populates="events")


class RepairCheckpointRecord(Base):
    __tablename__ = "repair_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("repair_sessions.id"), index=True)
    patch_revision: Mapped[str] = mapped_column(String(32), default="")
    patch: Mapped[str] = mapped_column(Text, default="")
    proposal_json: Mapped[str] = mapped_column(Text, default="{}")
    verification_json: Mapped[str] = mapped_column(Text, default="{}")
    candidate_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLogRecord(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(128), index=True, default="default")
    actor: Mapped[str] = mapped_column(String(255), default="anonymous")
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
