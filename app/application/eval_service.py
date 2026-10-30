from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from app.application.access import require_kb
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationFailed
from app.db.models import (
    EvaluationDatasetRecord,
    EvaluationItemRecord,
    ExperimentRecord,
)
from app.domain.schemas import PipelineConfig
from app.llm.factory import get_llm_client
from app.rag.document_index import PersistentDocumentIndex
from app.rag.embeddings import get_embedding_provider
from app.rag.metrics import hit_rate_at_k, mean, mrr, ndcg_at_k, precision_at_k, recall_at_k
from app.rag.pipeline import RagPipeline


def create_dataset(
    db: Session,
    *,
    workspace_id: str,
    name: str,
    description: str = "",
) -> EvaluationDatasetRecord:
    if not name.strip():
        raise ValidationFailed("Dataset name is required.")
    dataset = EvaluationDatasetRecord(
        id=str(uuid4()),
        workspace_id=workspace_id,
        name=name.strip(),
        description=description.strip(),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def add_item(
    db: Session,
    *,
    workspace_id: str,
    dataset_id: str,
    query: str,
    expected_answer: str | None = None,
    relevant_document_ids: list[str] | None = None,
) -> EvaluationItemRecord:
    dataset = db.get(EvaluationDatasetRecord, dataset_id)
    if dataset is None or dataset.workspace_id != workspace_id:
        raise NotFoundError("Dataset was not found in this workspace.")
    item = EvaluationItemRecord(
        id=str(uuid4()),
        dataset_id=dataset.id,
        query=query.strip(),
        expected_answer=expected_answer,
        relevant_document_ids_json=json.dumps(relevant_document_ids or []),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_dataset(db: Session, dataset_id: str, workspace_id: str) -> EvaluationDatasetRecord:
    dataset = db.get(EvaluationDatasetRecord, dataset_id)
    if dataset is None or dataset.workspace_id != workspace_id:
        raise NotFoundError("Dataset was not found in this workspace.")
    return dataset


def list_datasets(db: Session, workspace_id: str) -> list[EvaluationDatasetRecord]:
    return (
        db.query(EvaluationDatasetRecord)
        .filter(EvaluationDatasetRecord.workspace_id == workspace_id)
        .order_by(EvaluationDatasetRecord.created_at.desc())
        .all()
    )


def run_experiment(
    db: Session,
    *,
    workspace_id: str,
    name: str,
    knowledge_base_id: str,
    dataset_id: str,
    config: PipelineConfig | None = None,
) -> ExperimentRecord:
    kb = require_kb(db, knowledge_base_id, workspace_id)
    dataset = db.get(EvaluationDatasetRecord, dataset_id)
    if dataset is None or dataset.workspace_id != workspace_id:
        raise NotFoundError("Dataset was not found in this workspace.")
    cfg = config or PipelineConfig(generate_answer=False)
    if len(dataset.items) > settings.max_evaluation_items:
        raise ValidationFailed(
            f"Dataset has {len(dataset.items)} items; max_evaluation_items is {settings.max_evaluation_items}."
        )
    embedder = get_embedding_provider(
        cfg.embedding_provider or kb.embedding_provider,
        cfg.embedding_model or kb.embedding_model,
    )
    index = PersistentDocumentIndex.load(kb.id, kb.embedding_dimension, workspace_id)
    llm = get_llm_client(cfg.llm_provider) if cfg.generate_answer else None
    pipeline = RagPipeline(index=index, embedder=embedder, config=cfg, llm=llm)

    labeled = False
    rows = []
    p_at_k: list[float] = []
    r_at_k: list[float] = []
    mrr_scores: list[float] = []
    ndcg_scores: list[float] = []
    hits: list[float] = []

    for item in dataset.items:
        result = pipeline.query(item.query)
        retrieved_doc_ids = [chunk.chunk.document_id for chunk in result.retrieved]
        relevant = set(json.loads(item.relevant_document_ids_json or "[]"))
        row = {
            "item_id": item.id,
            "query": item.query,
            "retrieved_document_ids": retrieved_doc_ids,
            "answer": result.answer,
            "latencies_ms": result.latencies_ms,
        }
        if relevant:
            labeled = True
            k = cfg.top_k
            row["precision_at_k"] = precision_at_k(retrieved_doc_ids, relevant, k)
            row["recall_at_k"] = recall_at_k(retrieved_doc_ids, relevant, k)
            row["mrr"] = mrr(retrieved_doc_ids, relevant)
            row["ndcg_at_k"] = ndcg_at_k(retrieved_doc_ids, relevant, k)
            row["hit_rate_at_k"] = hit_rate_at_k(retrieved_doc_ids, relevant, k)
            p_at_k.append(row["precision_at_k"])
            r_at_k.append(row["recall_at_k"])
            mrr_scores.append(row["mrr"])
            ndcg_scores.append(row["ndcg_at_k"])
            hits.append(row["hit_rate_at_k"])
        rows.append(row)

    metrics = {
        "query_count": len(rows),
        "ground_truth_metrics_reported": labeled,
        "notes": (
            "Ranking metrics are reported only for items that include relevant_document_ids."
            if labeled
            else "No relevant document labels were provided, so ranking metrics were omitted."
        ),
    }
    if labeled:
        metrics.update(
            {
                "precision_at_k": round(mean(p_at_k), 4),
                "recall_at_k": round(mean(r_at_k), 4),
                "mrr": round(mean(mrr_scores), 4),
                "ndcg_at_k": round(mean(ndcg_scores), 4),
                "hit_rate_at_k": round(mean(hits), 4),
                "k": cfg.top_k,
            }
        )

    experiment = ExperimentRecord(
        id=str(uuid4()),
        workspace_id=workspace_id,
        name=name.strip() or "experiment",
        knowledge_base_id=kb.id,
        dataset_id=dataset.id,
        config_json=cfg.model_dump_json(),
        metrics_json=json.dumps(metrics),
        results_json=json.dumps(rows),
        status="completed",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def list_experiments(db: Session, workspace_id: str) -> list[ExperimentRecord]:
    return (
        db.query(ExperimentRecord)
        .filter(ExperimentRecord.workspace_id == workspace_id)
        .order_by(ExperimentRecord.created_at.desc())
        .all()
    )


def export_dataset(db: Session, dataset_id: str, workspace_id: str) -> dict:
    dataset = get_dataset(db, dataset_id, workspace_id)
    return {
        "format": "rag-debugger-dataset/v1",
        "name": dataset.name,
        "description": dataset.description,
        "items": [
            {
                "query": item.query,
                "expected_answer": item.expected_answer,
                "relevant_document_ids": json.loads(item.relevant_document_ids_json or "[]"),
            }
            for item in dataset.items
        ],
    }


def import_dataset(db: Session, workspace_id: str, payload: dict) -> EvaluationDatasetRecord:
    if not isinstance(payload, dict):
        raise ValidationFailed("Dataset import payload must be a JSON object.")
    items = payload.get("items")
    if items is None and isinstance(payload.get("queries"), list):
        items = payload["queries"]
    if not isinstance(items, list) or not items:
        raise ValidationFailed("Dataset import requires a non-empty items array.")
    dataset = create_dataset(
        db,
        workspace_id=workspace_id,
        name=str(payload.get("name") or "imported-dataset"),
        description=str(payload.get("description") or ""),
    )
    for raw in items:
        if not isinstance(raw, dict) or not str(raw.get("query") or "").strip():
            raise ValidationFailed("Each dataset item must include a query.")
        relevant = raw.get("relevant_document_ids") or raw.get("relevant_docs") or []
        if not isinstance(relevant, list):
            raise ValidationFailed("relevant_document_ids must be a list.")
        add_item(
            db,
            workspace_id=workspace_id,
            dataset_id=dataset.id,
            query=str(raw["query"]),
            expected_answer=raw.get("expected_answer"),
            relevant_document_ids=[str(item) for item in relevant],
        )
    db.refresh(dataset)
    return dataset


def export_experiment(db: Session, experiment_id: str, workspace_id: str) -> dict:
    experiment = db.get(ExperimentRecord, experiment_id)
    if experiment is None or experiment.workspace_id != workspace_id:
        raise NotFoundError("Experiment was not found in this workspace.")
    return {
        "format": "rag-debugger-experiment/v1",
        "id": experiment.id,
        "name": experiment.name,
        "status": experiment.status,
        "knowledge_base_id": experiment.knowledge_base_id,
        "dataset_id": experiment.dataset_id,
        "config": json.loads(experiment.config_json or "{}"),
        "metrics": json.loads(experiment.metrics_json or "{}"),
        "results": json.loads(experiment.results_json or "[]"),
        "created_at": experiment.created_at.isoformat() if experiment.created_at else None,
    }


def delete_experiment(db: Session, experiment_id: str, workspace_id: str) -> None:
    experiment = db.get(ExperimentRecord, experiment_id)
    if experiment is None or experiment.workspace_id != workspace_id:
        raise NotFoundError("Experiment was not found in this workspace.")
    db.delete(experiment)
    db.commit()


def delete_dataset(db: Session, dataset_id: str, workspace_id: str) -> None:
    dataset = get_dataset(db, dataset_id, workspace_id)
    db.delete(dataset)
    db.commit()


def reproduce_experiment(db: Session, experiment_id: str, workspace_id: str) -> ExperimentRecord:
    original = db.get(ExperimentRecord, experiment_id)
    if original is None or original.workspace_id != workspace_id:
        raise NotFoundError("Experiment was not found in this workspace.")
    config = PipelineConfig.model_validate(json.loads(original.config_json or "{}"))
    return run_experiment(
        db,
        workspace_id=workspace_id,
        name=f"{original.name} (reproduced)",
        knowledge_base_id=original.knowledge_base_id,
        dataset_id=original.dataset_id,
        config=config,
    )


def compare_experiments(db: Session, workspace_id: str, experiment_ids: list[str]) -> dict:
    rows = []
    for exp_id in experiment_ids:
        exp = db.get(ExperimentRecord, exp_id)
        if exp is None or exp.workspace_id != workspace_id:
            raise NotFoundError(f"Experiment {exp_id} was not found in this workspace.")
        rows.append(
            {
                "id": exp.id,
                "name": exp.name,
                "created_at": exp.created_at.isoformat() if exp.created_at else None,
                "config": json.loads(exp.config_json or "{}"),
                "metrics": json.loads(exp.metrics_json or "{}"),
            }
        )
    return {"experiments": rows}
