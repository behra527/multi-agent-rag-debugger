from fastapi.testclient import TestClient

from app.core.config import settings


def _create_kb(client: TestClient, workspace: str = "default") -> str:
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Policies", "description": "test kb", "embedding_provider": "hash"},
        headers={"X-Workspace-Id": workspace},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_ingest_query_debug_and_experiment(rag_client: TestClient):
    kb_id = _create_kb(rag_client)
    content = (
        "Refunds are issued within 14 days of purchase when the original receipt is provided. "
        "Shipping is available worldwide except for restricted destinations."
    )
    upload = rag_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("policy.txt", content.encode("utf-8"), "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    document = upload.json()
    assert document["status"] == "indexed"
    assert document["chunk_count"] >= 1

    query = rag_client.post(
        "/api/v1/rag/query",
        json={"knowledge_base_id": kb_id, "query": "When are refunds issued?"},
    )
    assert query.status_code == 200, query.text
    payload = query.json()
    assert payload["retrieved"]
    assert payload["answer"]
    assert "14 days" in payload["answer"] or "[1]" in payload["answer"]

    debug = rag_client.post(
        "/api/v1/debug/sessions",
        json={"knowledge_base_id": kb_id, "query": "When are refunds issued?"},
    )
    assert debug.status_code == 200, debug.text
    report = debug.json()["report"]
    assert report["findings"]
    assert report["root_causes"]
    assert report["query_result"]["retrieved"]
    assert "fabricated" not in report["executive_summary"].lower()

    dataset = rag_client.post("/api/v1/datasets", json={"name": "refunds"}).json()
    rag_client.post(
        f"/api/v1/datasets/{dataset['id']}/items",
        json={
            "query": "When are refunds issued?",
            "expected_answer": "within 14 days",
            "relevant_document_ids": [document["id"]],
        },
    )
    experiment = rag_client.post(
        "/api/v1/experiments",
        json={
            "name": "baseline",
            "knowledge_base_id": kb_id,
            "dataset_id": dataset["id"],
            "config": {"generate_answer": False, "top_k": 5, "retrieval_mode": "hybrid"},
        },
    )
    assert experiment.status_code == 200, experiment.text
    metrics = experiment.json()["metrics"]
    assert metrics["ground_truth_metrics_reported"] is True
    assert metrics["hit_rate_at_k"] >= 1.0

    overview = rag_client.get("/api/v1/overview")
    assert overview.status_code == 200
    assert overview.json()["knowledge_bases"] == 1
    assert overview.json()["source"] == "database"


def test_workspace_isolation(rag_client: TestClient):
    kb_id = _create_kb(rag_client, workspace="alpha")
    other = rag_client.get(
        f"/api/v1/knowledge-bases/{kb_id}",
        headers={"X-Workspace-Id": "beta"},
    )
    assert other.status_code in {403, 422, 404}


def test_rejects_unsupported_upload(rag_client: TestClient):
    kb_id = _create_kb(rag_client)
    response = rag_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("payload.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_rejects_oversized_upload(rag_client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 8)
    kb_id = _create_kb(rag_client)
    response = rag_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        files={"file": ("notes.txt", b"0123456789", "text/plain")},
    )
    assert response.status_code == 422
