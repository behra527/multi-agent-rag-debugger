from __future__ import annotations

from sqlalchemy.orm import Session

from app.application import eval_service, knowledge_service
from app.core.config import settings
from app.db.models import KnowledgeBaseRecord

SAMPLE_KB_NAME = "[Sample] Support policy"
SAMPLE_DATASET_NAME = "[Sample] Support evaluation"
SAMPLE_DOCUMENT = """SAMPLE ONBOARDING DOCUMENT
This file is an optional labeled sample for product onboarding. It is not hidden production data.

Refunds are issued within 14 days of purchase when the original receipt is provided.
Shipping is available worldwide except for restricted destinations.
Office hours are Monday through Friday.
"""
SAMPLE_QUERY = "When are refunds issued?"


def load_sample_workspace(db: Session, workspace_id: str) -> dict:
    existing = (
        db.query(KnowledgeBaseRecord)
        .filter(
            KnowledgeBaseRecord.workspace_id == workspace_id,
            KnowledgeBaseRecord.name == SAMPLE_KB_NAME,
        )
        .first()
    )
    if existing:
        kb = existing
        document = next(iter(kb.documents), None)
    else:
        kb = knowledge_service.create_knowledge_base(
            db,
            workspace_id=workspace_id,
            name=SAMPLE_KB_NAME,
            description="Optional labeled sample. Safe to delete.",
            embedding_provider=settings.embedding_provider,
        )
        document, _job = knowledge_service.ingest_document(
            db,
            knowledge_base_id=kb.id,
            workspace_id=workspace_id,
            filename="sample-support-policy.txt",
            data=SAMPLE_DOCUMENT.encode("utf-8"),
            content_type="text/plain",
        )

    dataset = next(
        (item for item in eval_service.list_datasets(db, workspace_id) if item.name == SAMPLE_DATASET_NAME),
        None,
    )
    if dataset is None:
        dataset = eval_service.create_dataset(
            db,
            workspace_id=workspace_id,
            name=SAMPLE_DATASET_NAME,
            description="Optional labeled sample queries for the sample knowledge base.",
        )
        eval_service.add_item(
            db,
            workspace_id=workspace_id,
            dataset_id=dataset.id,
            query=SAMPLE_QUERY,
            expected_answer="within 14 days of purchase",
            relevant_document_ids=[document.id] if document else [],
        )

    return {
        "sample": True,
        "knowledge_base_id": kb.id,
        "dataset_id": dataset.id,
        "document_id": document.id if document else None,
        "name": SAMPLE_KB_NAME,
        "note": "This is an optional labeled sample, not required application data.",
    }
