from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, File, Header, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application import audit, auth_service, debug_service, eval_service, knowledge_service, onboarding
from app.application.auth_service import Identity
from app.application import provider_status as provider_status_service
from app.api.deps import get_identity, get_workspace
from app.core.config import settings
from app.core.exceptions import ValidationFailed
from app.db.database import get_db
from app.db.models import (
    DebugSessionRecord,
    DocumentRecord,
    EvaluationDatasetRecord,
    ExperimentRecord,
    JobRecord,
    KnowledgeBaseRecord,
)
from app.domain.schemas import PipelineConfig

router = APIRouter(prefix="/api/v1")


def _audit(
    db: Session,
    workspace_id: str,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    message: str = "",
    actor: str = "anonymous",
) -> None:
    audit.record(
        db,
        workspace_id=workspace_id,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        message=message,
    )


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    chunk_size: int | None = Field(default=None, ge=64, le=8000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2000)
    embedding_provider: str | None = None
    embedding_model: str | None = None


class QueryRequest(BaseModel):
    knowledge_base_id: str
    query: str = Field(min_length=1)
    config: PipelineConfig | None = None


class DebugRequest(BaseModel):
    knowledge_base_id: str
    query: str = Field(min_length=1)
    config: PipelineConfig | None = None
    llm_provider: str | None = None


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""


class DatasetItemCreate(BaseModel):
    query: str = Field(min_length=1)
    expected_answer: str | None = None
    relevant_document_ids: list[str] = Field(default_factory=list)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1)
    knowledge_base_id: str
    dataset_id: str
    config: PipelineConfig | None = None


def _kb_payload(kb: KnowledgeBaseRecord) -> dict[str, Any]:
    return {
        "id": kb.id,
        "workspace_id": kb.workspace_id,
        "name": kb.name,
        "description": kb.description,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "embedding_provider": kb.embedding_provider,
        "embedding_model": kb.embedding_model,
        "embedding_dimension": kb.embedding_dimension,
        "document_count": kb.document_count,
        "chunk_count": kb.chunk_count,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
    }


def _doc_payload(doc: DocumentRecord) -> dict[str, Any]:
    return {
        "id": doc.id,
        "knowledge_base_id": doc.knowledge_base_id,
        "filename": doc.filename,
        "status": doc.status,
        "checksum": doc.checksum,
        "char_count": doc.char_count,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


class AuthRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


@router.post("/auth/register")
def register(payload: AuthRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user, token = auth_service.register_user(db, payload.email, payload.password)
    return {"email": user.email, "workspace_id": user.workspace_id, "token": token, "user_id": user.id}


@router.post("/auth/login")
def login(payload: AuthRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    user, token = auth_service.login_user(db, payload.email, payload.password)
    return {"email": user.email, "workspace_id": user.workspace_id, "token": token, "user_id": user.id}


@router.post("/auth/logout")
def logout(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    from app.core.exceptions import AuthorizationError

    try:
        auth_service.logout_user(db, authorization)
    except AuthorizationError:
        pass
    return {"status": "signed_out"}


@router.get("/auth/me")
def me(identity: Identity = Depends(get_identity)) -> dict[str, Any]:
    return {
        "workspace_id": identity.workspace_id,
        "user_id": identity.user_id,
        "email": identity.email,
        "actor": identity.actor,
        "auth_type": identity.auth_type,
        "auth_mode": settings.auth_mode,
    }


@router.get("/providers/status")
def providers_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return provider_status_service.collect_status(db)


@router.get("/audit")
def list_audit(
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    return [
        {
            "id": event.id,
            "action": event.action,
            "actor": event.actor,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "message": event.message,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in audit.list_events(db, workspace_id, limit=limit)
    ]


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/overview")
def product_metrics(
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    kb_count = (
        db.query(KnowledgeBaseRecord)
        .filter(KnowledgeBaseRecord.workspace_id == workspace_id)
        .count()
    )
    doc_count = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.workspace_id == workspace_id)
        .count()
    )
    session_count = (
        db.query(DebugSessionRecord)
        .filter(DebugSessionRecord.workspace_id == workspace_id)
        .count()
    )
    failed_ingest = (
        db.query(DocumentRecord)
        .filter(
            DocumentRecord.workspace_id == workspace_id,
            DocumentRecord.status == "failed",
        )
        .count()
    )
    experiments = (
        db.query(ExperimentRecord)
        .filter(ExperimentRecord.workspace_id == workspace_id)
        .count()
    )
    return {
        "knowledge_bases": kb_count,
        "documents": doc_count,
        "debug_sessions": session_count,
        "failed_ingestions": failed_ingest,
        "experiments": experiments,
        "source": "database",
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "auth_required": bool(settings.api_auth_token.strip()),
    }


@router.post("/knowledge-bases")
def create_kb(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    kb = knowledge_service.create_knowledge_base(
        db,
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        embedding_provider=payload.embedding_provider,
        embedding_model=payload.embedding_model,
    )
    _audit(db, workspace_id, "knowledge_base.create", "knowledge_base", kb.id, kb.name)
    return _kb_payload(kb)


@router.get("/knowledge-bases")
def list_kbs(
    response: Response,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    rows, total = knowledge_service.list_knowledge_bases(db, workspace_id, skip=skip, limit=limit)
    response.headers["X-Total-Count"] = str(total)
    return [_kb_payload(kb) for kb in rows]


@router.post("/onboarding/sample")
def load_sample(
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    return onboarding.load_sample_workspace(db, workspace_id)


@router.get("/knowledge-bases/{kb_id}")
def get_kb(
    kb_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    from app.application.access import require_kb

    kb = require_kb(db, kb_id, workspace_id)
    docs = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.knowledge_base_id == kb.id)
        .all()
    )
    payload = _kb_payload(kb)
    payload["documents"] = [_doc_payload(doc) for doc in docs]
    return payload


@router.delete("/knowledge-bases/{kb_id}")
def delete_kb(
    kb_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, str]:
    knowledge_service.delete_knowledge_base(db, kb_id, workspace_id)
    _audit(db, workspace_id, "knowledge_base.delete", "knowledge_base", kb_id)
    return {"status": "deleted", "id": kb_id}


@router.post("/knowledge-bases/{kb_id}/documents")
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    data = await file.read()
    document, job = knowledge_service.ingest_document(
        db,
        knowledge_base_id=kb_id,
        workspace_id=workspace_id,
        filename=file.filename or "upload.txt",
        data=data,
        content_type=file.content_type,
    )
    payload = _doc_payload(document)
    payload["job_id"] = job.id if job else None
    payload["duplicate"] = job is None
    _audit(db, workspace_id, "document.ingest", "document", document.id, document.filename)
    return payload


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, str]:
    knowledge_service.delete_document(db, document_id, workspace_id)
    return {"status": "deleted", "id": document_id}


@router.post("/knowledge-bases/{kb_id}/reindex")
def reindex(
    kb_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    return knowledge_service.reindex_knowledge_base(db, kb_id, workspace_id)


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    job = db.get(JobRecord, job_id)
    if job is None or job.workspace_id != workspace_id:
        raise ValidationFailed("Job was not found in this workspace.")
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error_message": job.error_message,
        "result": json.loads(job.result_json or "{}"),
    }


@router.post("/rag/query")
def rag_query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    result = debug_service.query_knowledge_base(
        db,
        workspace_id=workspace_id,
        knowledge_base_id=payload.knowledge_base_id,
        query=payload.query,
        config=payload.config,
    )
    return json.loads(result.model_dump_json())


@router.post("/debug/sessions")
def create_debug_session(
    payload: DebugRequest,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    session = debug_service.run_debug_session(
        db,
        workspace_id=workspace_id,
        knowledge_base_id=payload.knowledge_base_id,
        query=payload.query,
        config=payload.config,
        llm_provider=payload.llm_provider,
    )
    report = json.loads(session.report_json or "{}")
    _audit(db, workspace_id, "debug.run", "debug_session", session.id, payload.query[:200])
    return {
        "id": session.id,
        "status": session.status,
        "knowledge_base_id": session.knowledge_base_id,
        "query": session.query,
        "duration_ms": session.duration_ms,
        "error_message": session.error_message,
        "report": report,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.get("/debug/sessions")
def list_debug_sessions(
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    sessions = debug_service.list_sessions(db, workspace_id, limit=limit)
    return [
        {
            "id": s.id,
            "status": s.status,
            "knowledge_base_id": s.knowledge_base_id,
            "query": s.query,
            "duration_ms": s.duration_ms,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]


@router.get("/debug/sessions/{session_id}")
def get_debug_session(
    session_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    session = debug_service.get_session(db, session_id, workspace_id)
    return {
        "id": session.id,
        "status": session.status,
        "knowledge_base_id": session.knowledge_base_id,
        "query": session.query,
        "duration_ms": session.duration_ms,
        "error_message": session.error_message,
        "report": json.loads(session.report_json or "{}"),
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


@router.get("/reports/{session_id}")
def get_report(
    session_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    session = debug_service.get_session(db, session_id, workspace_id)
    return json.loads(session.report_json or "{}")


@router.post("/datasets")
def create_dataset(
    payload: DatasetCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    dataset = eval_service.create_dataset(
        db, workspace_id=workspace_id, name=payload.name, description=payload.description
    )
    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }


@router.get("/datasets")
def list_datasets(
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> list[dict[str, Any]]:
    datasets = eval_service.list_datasets(db, workspace_id)
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "item_count": len(d.items),
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in datasets
    ]


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    dataset = eval_service.get_dataset(db, dataset_id, workspace_id)
    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
        "items": [
            {
                "id": item.id,
                "query": item.query,
                "expected_answer": item.expected_answer,
                "relevant_document_ids": json.loads(item.relevant_document_ids_json or "[]"),
            }
            for item in dataset.items
        ],
    }


@router.post("/datasets/import")
def import_dataset(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    dataset = eval_service.import_dataset(db, workspace_id, payload)
    exported = eval_service.export_dataset(db, dataset.id, workspace_id)
    exported["id"] = dataset.id
    return exported


@router.get("/datasets/{dataset_id}/export")
def export_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    return eval_service.export_dataset(db, dataset_id, workspace_id)


@router.delete("/experiments/{experiment_id}")
def delete_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, str]:
    eval_service.delete_experiment(db, experiment_id, workspace_id)
    _audit(db, workspace_id, "experiment.delete", "experiment", experiment_id)
    return {"status": "deleted", "id": experiment_id}


@router.delete("/datasets/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, str]:
    eval_service.delete_dataset(db, dataset_id, workspace_id)
    return {"status": "deleted", "id": dataset_id}


@router.post("/datasets/{dataset_id}/items")
def add_dataset_item(
    dataset_id: str,
    payload: DatasetItemCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    item = eval_service.add_item(
        db,
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        query=payload.query,
        expected_answer=payload.expected_answer,
        relevant_document_ids=payload.relevant_document_ids,
    )
    return {
        "id": item.id,
        "dataset_id": item.dataset_id,
        "query": item.query,
        "expected_answer": item.expected_answer,
        "relevant_document_ids": json.loads(item.relevant_document_ids_json),
    }


@router.post("/experiments")
def create_experiment(
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    experiment = eval_service.run_experiment(
        db,
        workspace_id=workspace_id,
        name=payload.name,
        knowledge_base_id=payload.knowledge_base_id,
        dataset_id=payload.dataset_id,
        config=payload.config,
    )
    _audit(db, workspace_id, "experiment.run", "experiment", experiment.id, experiment.name)
    return _experiment_payload(experiment)


@router.get("/experiments")
def list_experiments(
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> list[dict[str, Any]]:
    experiments = eval_service.list_experiments(db, workspace_id)
    return [
        {
            "id": e.id,
            "name": e.name,
            "status": e.status,
            "knowledge_base_id": e.knowledge_base_id,
            "dataset_id": e.dataset_id,
            "metrics": json.loads(e.metrics_json or "{}"),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in experiments
    ]


def _experiment_payload(experiment) -> dict[str, Any]:
    return {
        "id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "knowledge_base_id": experiment.knowledge_base_id,
        "dataset_id": experiment.dataset_id,
        "metrics": json.loads(experiment.metrics_json or "{}"),
        "results": json.loads(experiment.results_json or "[]"),
        "config": json.loads(experiment.config_json or "{}"),
        "created_at": experiment.created_at.isoformat() if experiment.created_at else None,
    }


@router.post("/experiments/{experiment_id}/reproduce")
def reproduce_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    experiment = eval_service.reproduce_experiment(db, experiment_id, workspace_id)
    return _experiment_payload(experiment)


@router.get("/experiments/compare")
def compare_experiments(
    ids: str = Query(..., description="Comma-separated experiment IDs"),
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    return eval_service.compare_experiments(
        db, workspace_id, [item.strip() for item in ids.split(",") if item.strip()]
    )


@router.get("/experiments/{experiment_id}/export")
def export_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    return eval_service.export_experiment(db, experiment_id, workspace_id)


@router.get("/experiments/{experiment_id}")
def get_experiment(
    experiment_id: str,
    db: Session = Depends(get_db),
    workspace_id: str = Depends(get_workspace),
) -> dict[str, Any]:
    experiment = db.get(ExperimentRecord, experiment_id)
    if experiment is None or experiment.workspace_id != workspace_id:
        raise ValidationFailed("Experiment was not found in this workspace.")
    return {
        "id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "metrics": json.loads(experiment.metrics_json),
        "results": json.loads(experiment.results_json),
        "config": json.loads(experiment.config_json),
        "created_at": experiment.created_at.isoformat() if experiment.created_at else None,
    }
