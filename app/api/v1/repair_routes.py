from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.application.auth_service import Identity
from app.db.database import get_db
from app.db.models import RepairSessionRecord
from app.factory import create_repair_orchestrator
from app.core.config import settings
from app.repair.orchestrator import RepairOrchestrator
from app.repair.repos import is_allowed_path, list_authorized_repositories
from app.repair.schemas import RepairSession

router = APIRouter(prefix="/api/v1/repair", tags=["repair"])


class CreateSessionRequest(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    repository_path: str = Field(default="")
    repository_url: str | None = None
    branch: str | None = None
    traceback: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    extra_context: str = ""
    provider: str | None = None
    validation_command: list[str] | None = None
    max_iterations: int = Field(default=3, ge=1, le=5)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|revision_requested)$")
    patch_revision: str = Field(min_length=1)
    comment: str = ""


def _orch(provider: str | None = None) -> RepairOrchestrator:
    return create_repair_orchestrator(provider)


@router.get("/repositories")
def authorized_repositories() -> dict:
    return {
        "items": list_authorized_repositories(),
        "github_token_configured": bool(settings.github_token),
        "note": "The API can only read folders it is allowed to access. The browser cannot open arbitrary disks.",
    }


@router.post("/sessions", response_model=RepairSession)
def create_session(
    payload: CreateSessionRequest,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> RepairSession:
    workspace_id = identity.workspace_id
    path = payload.repository_path.strip()
    if not payload.repository_url and not path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide a local repository path or a GitHub URL.")
    if path:
        repo = Path(path).expanduser().resolve()
        if not repo.exists() or not repo.is_dir():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Local path is not a directory: {repo}")
        if not is_allowed_path(repo):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This folder is not in the authorized repository roots.")
        path = str(repo)
    orch = _orch(payload.provider)
    return orch.create_and_investigate(
        db,
        title=payload.title,
        description=payload.description,
        repository_path=path or str(Path("data/cloned")),
        traceback=payload.traceback,
        expected_behavior=payload.expected_behavior,
        actual_behavior=payload.actual_behavior,
        extra_context=payload.extra_context,
        repository_url=payload.repository_url,
        branch=payload.branch,
        workspace_id=workspace_id,
        actor=identity.email or identity.actor or "anonymous",
        max_iterations=payload.max_iterations,
        validation_command=payload.validation_command,
    )


@router.get("/sessions", response_model=list[RepairSession])
def list_sessions(
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> list[RepairSession]:
    workspace_id = identity.workspace_id
    orch = _orch()
    rows = (
        db.query(RepairSessionRecord)
        .filter(RepairSessionRecord.workspace_id == workspace_id)
        .order_by(RepairSessionRecord.created_at.desc())
        .limit(50)
        .all()
    )
    return [orch.to_schema(row) for row in rows]


@router.get("/sessions/{session_id}", response_model=RepairSession)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> RepairSession:
    workspace_id = identity.workspace_id
    row = db.get(RepairSessionRecord, session_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    return _orch().to_schema(row)


@router.post("/sessions/{session_id}/decision", response_model=RepairSession)
def decide(
    session_id: str,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> RepairSession:
    workspace_id = identity.workspace_id
    row = db.get(RepairSessionRecord, session_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    try:
        return _orch().decide(
            db,
            session_id,
            decision=payload.decision,
            actor=identity.email or identity.actor or "anonymous",
            patch_revision=payload.patch_revision,
            comment=payload.comment,
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/sessions/{session_id}/integrate", response_model=RepairSession)
def integrate(
    session_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> RepairSession:
    workspace_id = identity.workspace_id
    row = db.get(RepairSessionRecord, session_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    try:
        return _orch().integrate(db, session_id, actor=identity.email or identity.actor or "anonymous")
    except PermissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/sessions/{session_id}/cancel", response_model=RepairSession)
def cancel(
    session_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> RepairSession:
    workspace_id = identity.workspace_id
    row = db.get(RepairSessionRecord, session_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    try:
        return _orch().cancel(db, session_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/sessions/{session_id}/restore/{checkpoint_id}", response_model=RepairSession)
def restore_checkpoint(
    session_id: str,
    checkpoint_id: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> RepairSession:
    workspace_id = identity.workspace_id
    row = db.get(RepairSessionRecord, session_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    try:
        return _orch().restore_checkpoint(db, session_id, checkpoint_id)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Checkpoint not found.") from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/sessions/{session_id}/evidence")
def attach_evidence(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    identity: Identity = Depends(require_user),
) -> dict:
    workspace_id = identity.workspace_id
    row = db.get(RepairSessionRecord, session_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large.")
    folder = settings.upload_dir / "repair" / session_id
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:8]}-{(file.filename or 'evidence.bin')}"
    target = folder / Path(name).name
    target.write_bytes(data)
    extras = json.loads(row.extras_json or "{}")
    attachments = list(extras.get("attachments") or [])
    attachments.append({"filename": file.filename, "path": str(target), "content_type": file.content_type})
    extras["attachments"] = attachments
    row.extras_json = json.dumps(extras)
    db.commit()
    return {"attached": True, "filename": file.filename, "bytes": len(data)}
