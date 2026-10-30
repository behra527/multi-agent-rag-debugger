from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    source: str
    content: str
    start_line: int = 1
    end_line: int = 1
    score: float = 0.0


class InvestigationReport(BaseModel):
    diagnosis: str
    root_cause: str
    explanation: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    facts: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    target_found: bool = True
    issue_nature: str = "code"
    halt_reason: str | None = None


class FixProposal(BaseModel):
    summary: str
    patch: str
    patch_revision: str
    affected_files: list[str] = Field(default_factory=list)
    reasoning: str
    regressions: list[str] = Field(default_factory=list)
    verification_plan: list[str] = Field(default_factory=list)
    rollback_strategy: str = "Restore the isolated candidate from the previous checkpoint. Do not touch the target project."
    deletions: list[str] = Field(default_factory=list)


class VerificationReport(BaseModel):
    passed: bool
    command: list[str] = Field(default_factory=list)
    exit_ok: bool = False
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    output: str = ""
    errors: list[str] = Field(default_factory=list)
    original_error_reproduced: bool | None = None
    remaining_blockers: list[str] = Field(default_factory=list)
    iteration: int = 0


class AgentEvent(BaseModel):
    agent: str
    status: str
    message: str
    duration_ms: float | None = None
    created_at: str | None = None


class RepairSession(BaseModel):
    id: str
    state: str
    title: str
    description: str
    traceback: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    extra_context: str = ""
    repository_kind: str = "local"
    repository_path: str
    repository_url: str | None = None
    revision_sha: str | None = None
    investigation: InvestigationReport | None = None
    proposal: FixProposal | None = None
    verification: VerificationReport | None = None
    current_patch_revision: str | None = None
    approved_patch_revision: str | None = None
    candidate_path: str | None = None
    iteration: int = 0
    max_iterations: int = 3
    actor: str = "anonymous"
    message: str = ""
    events: list[AgentEvent] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
