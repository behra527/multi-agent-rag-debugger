from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agents.orchestrator import DebugOrchestrator
from app.application.access import require_kb
from app.core.exceptions import AppError, ValidationFailed
from app.db.models import DebugSessionRecord
from app.domain.schemas import PipelineConfig
from app.llm.factory import get_llm_client
from app.rag.document_index import PersistentDocumentIndex
from app.rag.embeddings import get_embedding_provider


def run_debug_session(
    db: Session,
    *,
    workspace_id: str,
    knowledge_base_id: str,
    query: str,
    config: PipelineConfig | None = None,
    llm_provider: str | None = None,
) -> DebugSessionRecord:
    if not query.strip():
        raise ValidationFailed("Query is required.")
    kb = require_kb(db, knowledge_base_id, workspace_id)
    cfg = config or PipelineConfig(
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        embedding_provider=kb.embedding_provider,
        embedding_model=kb.embedding_model,
    )
    session = DebugSessionRecord(
        id=str(uuid4()),
        workspace_id=workspace_id,
        knowledge_base_id=kb.id,
        query=query.strip(),
        status="running",
        config_json=cfg.model_dump_json(),
    )
    db.add(session)
    db.commit()

    try:
        embedder = get_embedding_provider(
            cfg.embedding_provider or kb.embedding_provider,
            cfg.embedding_model or kb.embedding_model,
        )
        index = PersistentDocumentIndex.load(kb.id, kb.embedding_dimension, workspace_id)
        llm = get_llm_client(llm_provider or cfg.llm_provider)
        orchestrator = DebugOrchestrator(llm=llm, embedder=embedder)
        report = orchestrator.run(
            knowledge_base_id=kb.id,
            workspace_id=workspace_id,
            query=query.strip(),
            config=cfg,
            index=index,
            embedding_provider_name=embedder.provider_name,
            embedding_model=embedder.model_name,
            session_id=session.id,
        )
        session.status = "completed"
        session.report_json = report.model_dump_json()
        session.duration_ms = report.duration_ms
        db.commit()
        db.refresh(session)
        return session
    except Exception as exc:
        session.status = "failed"
        session.error_message = str(exc)
        db.commit()
        db.refresh(session)
        if isinstance(exc, AppError):
            raise
        raise AppError(f"Debug session failed: {exc}", code="debug_failed", status_code=500) from exc


def list_sessions(db: Session, workspace_id: str, limit: int = 50) -> list[DebugSessionRecord]:
    return (
        db.query(DebugSessionRecord)
        .filter(DebugSessionRecord.workspace_id == workspace_id)
        .order_by(DebugSessionRecord.created_at.desc())
        .limit(limit)
        .all()
    )


def get_session(db: Session, session_id: str, workspace_id: str) -> DebugSessionRecord:
    session = db.get(DebugSessionRecord, session_id)
    if session is None or session.workspace_id != workspace_id:
        raise ValidationFailed("Debug session was not found in this workspace.")
    return session


def query_knowledge_base(
    db: Session,
    *,
    workspace_id: str,
    knowledge_base_id: str,
    query: str,
    config: PipelineConfig | None = None,
    llm_provider: str | None = None,
):
    kb = require_kb(db, knowledge_base_id, workspace_id)
    cfg = config or PipelineConfig(
        chunk_size=kb.chunk_size,
        chunk_overlap=kb.chunk_overlap,
        generate_answer=True,
    )
    embedder = get_embedding_provider(
        cfg.embedding_provider or kb.embedding_provider,
        cfg.embedding_model or kb.embedding_model,
    )
    index = PersistentDocumentIndex.load(kb.id, kb.embedding_dimension, workspace_id)
    from app.rag.pipeline import RagPipeline

    llm = get_llm_client(llm_provider or cfg.llm_provider) if cfg.generate_answer else None
    pipeline = RagPipeline(index=index, embedder=embedder, config=cfg, llm=llm)
    return pipeline.query(query)
