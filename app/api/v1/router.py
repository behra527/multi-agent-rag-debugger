import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import IssueRequest
from app.core.report import FinalDebuggingReport
from app.db.database import get_db
from app.db.repository_service import PersistenceService
from app.factory import create_project_manager
from app.rag.scanner import RepositoryScanner

router = APIRouter(prefix="/api/v1")


# Schemas
class HealthStatusResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_provider: str
    database: str


class ScanRepositoryRequest(BaseModel):
    repository_path: str = Field(min_length=1)


class RepositoryInfoResponse(BaseModel):
    path: str
    exists: bool
    is_directory: bool
    total_files: int
    files: list[str]


class RunDebugRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    repository_path: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    use_langgraph: bool = False
    provider: str | None = None
    validation_command: list[str] | None = None


class ApprovalSubmissionRequest(BaseModel):
    status: str = Field(pattern="^(approved|rejected|revision_requested)$")
    reviewer: str = Field(default="developer")
    comment: str | None = None


class SettingsUpdateRequest(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    openai_model: str | None = None
    ollama_model: str | None = None
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None


# Endpoints
@router.get("/health", response_model=HealthStatusResponse)
def health_check(db: Session = Depends(get_db)) -> HealthStatusResponse:
    """Check health status of backend API, LLM provider, and database connectivity."""
    db_status = "connected"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    return HealthStatusResponse(
        status="ok",
        service="multi-agent-rag-debugger",
        version="1.0.0",
        llm_provider=settings.llm_provider,
        database=db_status,
    )


@router.get("/metrics")
def get_operational_metrics(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return genuine aggregated metrics calculated from persisted runs."""
    return PersistenceService.get_metrics(db)


@router.post("/repositories/scan", response_model=RepositoryInfoResponse)
def scan_repository(payload: ScanRepositoryRequest) -> RepositoryInfoResponse:
    """Scan a local directory and return discovered source files."""
    repo_path = Path(payload.repository_path).expanduser().resolve()

    if not repo_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path does not exist: {repo_path}",
        )

    if not repo_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path is not a directory: {repo_path}",
        )

    scanner = RepositoryScanner()
    files = scanner.scan(repo_path)
    relative_files = [p.relative_to(repo_path).as_posix() for p in files]

    return RepositoryInfoResponse(
        path=str(repo_path),
        exists=True,
        is_directory=True,
        total_files=len(files),
        files=relative_files[:100],  # Return up to 100 preview files
    )


@router.post("/debugging-runs", response_model=FinalDebuggingReport)
def create_debugging_run(
    payload: RunDebugRequest,
    db: Session = Depends(get_db),
) -> FinalDebuggingReport:
    """Execute the multi-agent debugging workflow and persist the final report."""
    repo_path = Path(payload.repository_path).expanduser().resolve()

    if not repo_path.exists() or not repo_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository path must be an existing directory.",
        )

    issue = IssueRequest(
        title=payload.title,
        description=payload.description,
        repository_path=str(repo_path),
    )

    try:
        manager = create_project_manager(
            use_langgraph=payload.use_langgraph,
            provider=payload.provider,
        )
        report = manager.handle_issue(
            issue=issue,
            top_k=payload.top_k,
            validation_command=payload.validation_command,
        )

        # Persist report to database
        PersistenceService.save_report(report, db)
        return report

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/debugging-runs")
def list_debugging_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List historical debugging sessions with pagination and search."""
    records = PersistenceService.list_runs(
        db=db,
        skip=skip,
        limit=limit,
        status=status_filter,
        search=search,
    )

    results = []
    for r in records:
        results.append({
            "run_id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "status": r.status,
            "title": r.title,
            "description": r.description,
            "repository_path": r.repository_path,
            "duration_ms": r.duration_ms,
            "message": r.message,
            "approval_status": r.approval_status,
            "has_fix": r.proposed_fix is not None,
            "validation_passed": r.validation.passed if r.validation else None,
        })
    return results


@router.get("/debugging-runs/{run_id}")
def get_debugging_run_detail(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full detail for a debugging run."""
    run = PersistenceService.get_run(run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debugging run {run_id} not found.",
        )

    return {
        "run_id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "status": run.status,
        "title": run.title,
        "description": run.description,
        "repository_path": run.repository_path,
        "duration_ms": run.duration_ms,
        "message": run.message,
        "approval_status": run.approval_status,
        "analysis": {
            "issue_type": run.analysis.issue_type,
            "priority": run.analysis.priority,
            "summary": run.analysis.summary,
            "affected_components": run.analysis.affected_components,
            "search_queries": run.analysis.search_queries,
        } if run.analysis else None,
        "root_cause": {
            "root_cause": run.root_cause.root_cause,
            "explanation": run.root_cause.explanation,
            "affected_files": json.loads(run.root_cause.affected_files_json),
            "evidence": json.loads(run.root_cause.evidence_json),
            "confidence": run.root_cause.confidence,
        } if run.root_cause else None,
        "proposed_fix": {
            "summary": run.proposed_fix.summary,
            "affected_files": json.loads(run.proposed_fix.affected_files_json),
            "patch": run.proposed_fix.patch,
            "reasoning": run.proposed_fix.reasoning,
        } if run.proposed_fix else None,
        "validation": {
            "passed": run.validation.passed,
            "tests_run": run.validation.tests_run,
            "tests_passed": run.validation.tests_passed,
            "tests_failed": run.validation.tests_failed,
            "output": run.validation.output,
            "errors": json.loads(run.validation.errors_json),
            "attempts": run.validation.attempts,
        } if run.validation else None,
        "evidence_count": len(run.evidence_items),
        "stage_traces": [
            {
                "stage": st.stage,
                "status": st.status,
                "started_at": st.started_at.isoformat() if st.started_at else None,
                "finished_at": st.finished_at.isoformat() if st.finished_at else None,
                "duration_ms": st.duration_ms,
                "error_type": st.error_type,
                "error_message": st.error_message,
            }
            for st in run.stage_traces
        ],
        "approval_history": [
            {
                "status": ap.status,
                "reviewer": ap.reviewer,
                "comment": ap.comment,
                "reviewed_at": ap.reviewed_at.isoformat() if ap.reviewed_at else None,
            }
            for ap in run.approval_history
        ],
    }


@router.get("/debugging-runs/{run_id}/evidence")
def get_run_evidence(
    run_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve ranked code evidence items for a debugging run."""
    run = PersistenceService.get_run(run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debugging run {run_id} not found.",
        )

    return [
        {
            "source": ev.source,
            "content": ev.content,
            "score": ev.score,
            "start_line": ev.start_line,
            "end_line": ev.end_line,
            "language": ev.language,
            "symbols": json.loads(ev.symbols_json),
        }
        for ev in run.evidence_items
    ]


@router.get("/debugging-runs/{run_id}/patch")
def get_run_patch(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve the unified git diff patch for a debugging run."""
    run = PersistenceService.get_run(run_id, db)
    if not run or not run.proposed_fix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No patch available for run {run_id}.",
        )

    return {
        "run_id": run.id,
        "summary": run.proposed_fix.summary,
        "affected_files": json.loads(run.proposed_fix.affected_files_json),
        "patch": run.proposed_fix.patch,
        "reasoning": run.proposed_fix.reasoning,
    }


@router.post("/debugging-runs/{run_id}/approval")
def submit_approval(
    run_id: str,
    payload: ApprovalSubmissionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit a human-in-the-loop review decision for a proposed fix.

    Approval is blocked when validation failed, unless the reviewer explicitly
    provides an override_reason explaining why they are overriding failed checks.
    """
    run = PersistenceService.get_run(run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debugging run {run_id} not found.",
        )

    # Block approval (but not rejection) when validation failed.
    if payload.status == "approved":
        if run.validation is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cannot approve a run that has not been validated. "
                    "Validation must complete before approval."
                ),
            )
        if not run.validation.passed:
            override_reason = payload.comment or ""
            if not override_reason.strip():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Validation failed for this run. Approval is blocked. "
                        "If you intend to override failed validation, "
                        "provide an explicit override_reason in the comment field. "
                        "This override will be recorded in the audit log."
                    ),
                )
            # Allow override but log it as an exception
            payload = ApprovalSubmissionRequest(
                status=payload.status,
                reviewer=payload.reviewer,
                comment=f"[VALIDATION OVERRIDE] {override_reason}",
            )

    try:
        approval = PersistenceService.record_approval(
            run_id=run_id,
            status=payload.status,
            reviewer=payload.reviewer,
            comment=payload.comment,
            db=db,
        )
        is_override = payload.comment and "[VALIDATION OVERRIDE]" in (payload.comment or "")
        return {
            "run_id": run_id,
            "approval_status": approval.status,
            "reviewer": approval.reviewer,
            "reviewed_at": approval.reviewed_at.isoformat(),
            "comment": approval.comment,
            "validation_override": is_override,
            "merge_ready": (
                approval.status == "approved"
                and (run.validation is not None and run.validation.passed)
            ),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/settings")
def get_runtime_settings() -> dict[str, Any]:
    """Retrieve current runtime configuration."""
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "openai_model": settings.openai_model,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "llm_temperature": settings.llm_temperature,
        "llm_max_tokens": settings.llm_max_tokens,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": settings.embedding_dimension,
        "auth_required": bool(settings.api_auth_token.strip()),
        "max_upload_bytes": settings.max_upload_bytes,
        "max_context_chars": settings.max_context_chars,
        "max_llm_calls_per_workflow": settings.max_llm_calls_per_workflow,
        "max_workflow_seconds": settings.max_workflow_seconds,
        "job_execution_mode": settings.job_execution_mode,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "max_evaluation_items": settings.max_evaluation_items,
        "auth_mode": settings.auth_mode,
        "reranker": settings.reranker,
        "database_url": settings.database_url.split("@")[-1],  # redact credentials if any
        "sandbox_timeout_seconds": settings.sandbox_timeout_seconds,
    }


@router.post("/settings")
def update_runtime_settings(payload: SettingsUpdateRequest) -> dict[str, Any]:
    """Update active model, provider, or inference parameters at runtime."""
    if payload.llm_provider is not None:
        settings.llm_provider = payload.llm_provider
    if payload.llm_model is not None:
        settings.llm_model = payload.llm_model
    if payload.openai_model is not None:
        settings.openai_model = payload.openai_model
    if payload.ollama_model is not None:
        settings.ollama_model = payload.ollama_model
    if payload.llm_temperature is not None:
        settings.llm_temperature = payload.llm_temperature
    if payload.llm_max_tokens is not None:
        settings.llm_max_tokens = payload.llm_max_tokens

    # Settings are applied immediately; new project managers are created per request.
    return get_runtime_settings()


# Git Schemas
class GitStatusQuery(BaseModel):
    repository_path: str = Field(min_length=1)


class GitCreateBranchRequest(BaseModel):
    repository_path: str = Field(min_length=1)
    branch_name: str = Field(min_length=1)
    base_branch: str | None = None


class GitCommitRequest(BaseModel):
    repository_path: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    branch_name: str | None = None
    commit_message: str | None = None
    author_name: str = Field(default="Multi-Agent RAG Debugger")
    author_email: str = Field(default="debugger@local")


class GitCloneRequest(BaseModel):
    remote_url: str = Field(min_length=1)
    target_directory: str = Field(min_length=1)
    branch: str | None = None


@router.get("/git/status")
def get_git_status(repository_path: str = Query(..., min_length=1)) -> dict[str, Any]:
    """Inspect Git repository metadata, branch, and working-tree status."""
    from app.tools.git_service import GitService

    repo_p = Path(repository_path).expanduser().resolve()
    if not repo_p.exists() or not repo_p.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path is not a valid directory: {repo_p}",
        )
    info = GitService.get_repository_info(repo_p)
    return info.model_dump()


@router.get("/git/commits")
def list_git_commits(
    repository_path: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Retrieve recent commits for the repository."""
    from app.tools.git_service import GitService

    repo_p = Path(repository_path).expanduser().resolve()
    if not repo_p.exists() or not repo_p.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path is not a valid directory: {repo_p}",
        )
    commits = GitService.list_recent_commits(repo_p, limit=limit)
    return [c.model_dump() for c in commits]


@router.post("/git/branch")
def create_git_branch(payload: GitCreateBranchRequest) -> dict[str, Any]:
    """Create a new isolated branch for a fix."""
    from app.tools.git_service import GitService

    repo_p = Path(payload.repository_path).expanduser().resolve()
    if not repo_p.exists() or not repo_p.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path is not a valid directory: {repo_p}",
        )
    try:
        res = GitService.create_fix_branch(
            repo_path=repo_p,
            branch_name=payload.branch_name,
            base_branch=payload.base_branch,
        )
        return res
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/git/commit")
def commit_approved_patch_endpoint(
    payload: GitCommitRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Commit an approved patch to the repository."""
    from app.tools.git_service import GitService

    run = PersistenceService.get_run(payload.run_id, db)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debugging run {payload.run_id} not found.",
        )
    if not run.proposed_fix or not run.proposed_fix.patch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No patch available to commit for this run.",
        )

    # Security check: must be approved by reviewer
    if run.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Commit blocked: the patch has not been approved. "
                "Explicit human approval is required prior to git commit."
            ),
        )

    repo_p = Path(payload.repository_path).expanduser().resolve()
    if not repo_p.exists() or not repo_p.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Repository path is not a valid directory: {repo_p}",
        )

    default_msg = f"fix({run.title}): {run.proposed_fix.summary}"
    try:
        res = GitService.commit_approved_patch(
            repo_path=repo_p,
            patch=run.proposed_fix.patch,
            commit_message=payload.commit_message or default_msg,
            branch_name=payload.branch_name,
            author_name=payload.author_name,
            author_email=payload.author_email,
        )
        return res
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/git/clone")
def clone_repository_endpoint(payload: GitCloneRequest) -> dict[str, Any]:
    """Clone a remote Git repository securely."""
    from app.tools.git_service import GitService

    target_p = Path(payload.target_directory).expanduser().resolve()
    try:
        res = GitService.clone_repository(
            remote_url=payload.remote_url,
            target_dir=target_p,
            branch=payload.branch,
        )
        return res
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
