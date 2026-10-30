from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.application.access import require_kb
from app.core.config import settings
from app.core.exceptions import IngestionError, ValidationFailed
from app.core.security import validate_upload
from app.db.database import SessionLocal
from app.db.models import DocumentRecord, JobRecord, KnowledgeBaseRecord
from app.domain.enums import DocumentStatus, JobStatus
from app.rag.document_index import PersistentDocumentIndex
from app.rag.embeddings import get_embedding_provider
from app.rag.ingestion import content_sha256, extract_text, normalize_text
from app.rag.text_chunker import chunk_text, chunking_stats


def create_knowledge_base(
    db: Session,
    *,
    workspace_id: str,
    name: str,
    description: str = "",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_provider: str | None = None,
    embedding_model: str | None = None,
) -> KnowledgeBaseRecord:
    if not name.strip():
        raise ValidationFailed("Knowledge base name is required.")
    kb = KnowledgeBaseRecord(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=name.strip(),
        description=description.strip(),
        chunk_size=chunk_size or settings.default_chunk_size,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.default_chunk_overlap,
        embedding_provider=embedding_provider or settings.embedding_provider,
        embedding_model=embedding_model or settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def list_knowledge_bases(
    db: Session,
    workspace_id: str,
    *,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[KnowledgeBaseRecord], int]:
    query = db.query(KnowledgeBaseRecord).filter(KnowledgeBaseRecord.workspace_id == workspace_id)
    total = query.count()
    rows = (
        query.order_by(KnowledgeBaseRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows, total


def delete_knowledge_base(db: Session, knowledge_base_id: str, workspace_id: str) -> None:
    kb = require_kb(db, knowledge_base_id, workspace_id)
    index = PersistentDocumentIndex(kb.id, kb.embedding_dimension, workspace_id)
    index.delete()
    upload_root = settings.upload_dir / workspace_id / kb.id
    if upload_root.exists():
        for path in upload_root.glob("*"):
            path.unlink(missing_ok=True)
    db.delete(kb)
    db.commit()


def ingest_document(
    db: Session,
    *,
    knowledge_base_id: str,
    workspace_id: str,
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> tuple[DocumentRecord, JobRecord | None]:
    kb = require_kb(db, knowledge_base_id, workspace_id)
    if kb.document_count >= settings.max_documents_per_kb:
        raise ValidationFailed("Knowledge base document limit reached.")
    safe_name = validate_upload(filename, len(data), content_type)
    checksum = content_sha256(data)

    existing = (
        db.query(DocumentRecord)
        .filter(
            DocumentRecord.knowledge_base_id == kb.id,
            DocumentRecord.checksum == checksum,
            DocumentRecord.workspace_id == workspace_id,
        )
        .first()
    )
    if existing:
        return existing, None

    doc_id = str(uuid.uuid4())
    storage_dir = settings.upload_dir / workspace_id / kb.id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{doc_id}_{safe_name}"
    storage_path.write_bytes(data)

    document = DocumentRecord(
        id=doc_id,
        knowledge_base_id=kb.id,
        workspace_id=workspace_id,
        filename=safe_name,
        content_type=content_type or "application/octet-stream",
        checksum=checksum,
        storage_path=str(storage_path),
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    job = JobRecord(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        job_type="ingestion",
        status=JobStatus.QUEUED.value,
        payload_json=json.dumps({"document_id": document.id, "knowledge_base_id": kb.id}),
        message="Queued for ingestion",
    )
    db.add(job)
    db.commit()

    if settings.job_execution_mode == "background":
        worker = threading.Thread(target=_ingest_in_thread, args=(job.id,), daemon=True)
        worker.start()
        return document, job

    process_ingestion_job(db, job.id)
    db.refresh(document)
    db.refresh(job)
    return document, job


def _ingest_in_thread(job_id: str) -> None:
    session = SessionLocal()
    try:
        process_ingestion_job(session, job_id)
    finally:
        session.close()


def process_ingestion_job(db: Session, job_id: str) -> JobRecord:
    job = db.get(JobRecord, job_id)
    if job is None:
        raise IngestionError(f"Job {job_id} was not found.")
    payload = json.loads(job.payload_json or "{}")
    document = db.get(DocumentRecord, payload["document_id"])
    kb = db.get(KnowledgeBaseRecord, payload["knowledge_base_id"])
    if document is None or kb is None:
        job.status = JobStatus.FAILED.value
        job.error_message = "Document or knowledge base missing."
        db.commit()
        return job

    job.status = JobStatus.RUNNING.value
    job.started_at = datetime.now(timezone.utc)
    job.progress = 0.1
    db.commit()

    try:
        document.status = DocumentStatus.EXTRACTING.value
        db.commit()
        raw = Path(document.storage_path).read_bytes()
        text = normalize_text(extract_text(Path(document.storage_path), raw))
        if not text.strip():
            raise IngestionError("Document contained no extractable text.")
        document.char_count = len(text)
        job.progress = 0.35

        document.status = DocumentStatus.CHUNKING.value
        db.commit()
        chunks = chunk_text(
            text,
            knowledge_base_id=kb.id,
            document_id=document.id,
            source=document.filename,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            metadata={"filename": document.filename, "checksum": document.checksum},
        )
        if not chunks:
            raise IngestionError("Chunking produced no passages.")
        if len(chunks) > settings.max_chunks_per_document:
            chunks = chunks[: settings.max_chunks_per_document]
        document.chunk_count = len(chunks)
        job.progress = 0.55
        document.status = DocumentStatus.EMBEDDING.value
        db.commit()

        embedder = get_embedding_provider(kb.embedding_provider, kb.embedding_model)
        embeddings = embedder.embed([chunk.content for chunk in chunks])
        kb.embedding_dimension = len(embeddings[0])
        embedder.dimension = kb.embedding_dimension

        index = PersistentDocumentIndex.load(kb.id, kb.embedding_dimension, kb.workspace_id)
        if index.dimension != kb.embedding_dimension:
            index = PersistentDocumentIndex(kb.id, kb.embedding_dimension, kb.workspace_id)
        index.add(embeddings, chunks)
        index.save()

        document.status = DocumentStatus.INDEXED.value
        db.flush()
        kb.document_count = (
            db.query(DocumentRecord)
            .filter(
                DocumentRecord.knowledge_base_id == kb.id,
                DocumentRecord.status == DocumentStatus.INDEXED.value,
            )
            .count()
        )
        kb.chunk_count = len(index.chunks)
        kb.updated_at = datetime.now(timezone.utc)
        job.status = JobStatus.COMPLETED.value
        job.progress = 1.0
        job.message = "Ingestion completed"
        job.result_json = json.dumps(chunking_stats(chunks))
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return job
    except Exception as exc:
        document.status = DocumentStatus.FAILED.value
        document.error_message = str(exc)
        job.status = JobStatus.FAILED.value
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        raise IngestionError(f"Ingestion failed: {exc}") from exc


def delete_document(db: Session, document_id: str, workspace_id: str) -> None:
    document = db.get(DocumentRecord, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise ValidationFailed("Document was not found in this workspace.")
    kb = require_kb(db, document.knowledge_base_id, workspace_id)
    Path(document.storage_path).unlink(missing_ok=True)

    index = PersistentDocumentIndex.load(kb.id, kb.embedding_dimension, workspace_id)
    remaining = [chunk for chunk in index.chunks if chunk.document_id != document.id]
    if remaining:
        embedder = get_embedding_provider(kb.embedding_provider, kb.embedding_model)
        rebuilt = PersistentDocumentIndex(kb.id, kb.embedding_dimension, workspace_id)
        embeddings = embedder.embed([chunk.content for chunk in remaining])
        rebuilt.add(embeddings, remaining)
        rebuilt.save()
        kb.chunk_count = len(remaining)
    else:
        index.delete()
        kb.chunk_count = 0
    db.delete(document)
    kb.document_count = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.knowledge_base_id == kb.id)
        .count()
        - 1
    )
    db.commit()


def reindex_knowledge_base(db: Session, knowledge_base_id: str, workspace_id: str) -> dict:
    kb = require_kb(db, knowledge_base_id, workspace_id)
    documents = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.knowledge_base_id == kb.id)
        .all()
    )
    embedder = get_embedding_provider(kb.embedding_provider, kb.embedding_model)
    rebuilt = PersistentDocumentIndex(kb.id, kb.embedding_dimension, workspace_id)
    rebuilt.delete()
    all_chunks = []
    for document in documents:
        raw = Path(document.storage_path).read_bytes()
        text = normalize_text(extract_text(Path(document.storage_path), raw))
        chunks = chunk_text(
            text,
            knowledge_base_id=kb.id,
            document_id=document.id,
            source=document.filename,
            chunk_size=kb.chunk_size,
            chunk_overlap=kb.chunk_overlap,
            metadata={"filename": document.filename},
        )
        embeddings = embedder.embed([chunk.content for chunk in chunks]) if chunks else []
        if embeddings:
            kb.embedding_dimension = len(embeddings[0])
            if rebuilt.dimension != kb.embedding_dimension:
                rebuilt = PersistentDocumentIndex(kb.id, kb.embedding_dimension, workspace_id)
        rebuilt.add(embeddings, chunks)
        document.chunk_count = len(chunks)
        document.status = DocumentStatus.INDEXED.value
        all_chunks.extend(chunks)
    rebuilt.save()
    kb.chunk_count = len(all_chunks)
    kb.document_count = len(documents)
    kb.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"chunk_count": kb.chunk_count, "document_count": kb.document_count}
