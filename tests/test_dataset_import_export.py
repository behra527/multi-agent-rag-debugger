from fastapi.testclient import TestClient


def test_dataset_roundtrip_and_experiment_export(rag_client: TestClient):
    imported = rag_client.post(
        "/api/v1/datasets/import",
        json={
            "name": "imported-refunds",
            "description": "fixture",
            "items": [
                {
                    "query": "When are refunds issued?",
                    "expected_answer": "within 14 days",
                    "relevant_document_ids": ["doc-1"],
                }
            ],
        },
    )
    assert imported.status_code == 200, imported.text
    dataset_id = imported.json()["id"]
    assert imported.json()["items"][0]["query"].startswith("When are refunds")

    exported = rag_client.get(f"/api/v1/datasets/{dataset_id}/export")
    assert exported.status_code == 200
    assert exported.json()["format"] == "rag-debugger-dataset/v1"
    assert len(exported.json()["items"]) == 1

    kb = rag_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "eval-kb", "embedding_provider": "hash"},
    ).json()
    rag_client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("policy.txt", b"Refunds are issued within 14 days.", "text/plain")},
    )
    experiment = rag_client.post(
        "/api/v1/experiments",
        json={
            "name": "imported-run",
            "knowledge_base_id": kb["id"],
            "dataset_id": dataset_id,
            "config": {"generate_answer": False, "retrieval_mode": "lexical"},
        },
    )
    assert experiment.status_code == 200, experiment.text
    bundle = rag_client.get(f"/api/v1/experiments/{experiment.json()['id']}/export")
    assert bundle.status_code == 200
    assert bundle.json()["format"] == "rag-debugger-experiment/v1"
    assert "metrics" in bundle.json()
