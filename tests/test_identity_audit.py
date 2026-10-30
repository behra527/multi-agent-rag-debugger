from fastapi.testclient import TestClient

from app.core.config import settings


def test_register_login_and_workspace_isolation(rag_client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "required")
    denied = rag_client.get("/api/v1/overview")
    assert denied.status_code == 401

    created = rag_client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password1"},
    )
    assert created.status_code == 200, created.text
    token = created.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    kb = rag_client.post("/api/v1/knowledge-bases", json={"name": "private"}, headers=headers)
    assert kb.status_code == 200, kb.text
    kb_id = kb.json()["id"]

    other = rag_client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "password1"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}
    hidden = rag_client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=other_headers)
    assert hidden.status_code in {403, 404}

    visible = rag_client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=headers)
    assert visible.status_code == 200
    events = rag_client.get("/api/v1/audit", headers=headers)
    assert events.status_code == 200
    assert any(item["action"] == "knowledge_base.create" for item in events.json())


def test_repair_inbox_is_private_per_account(rag_client: TestClient, tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")

    denied = rag_client.get("/api/v1/repair/sessions")
    assert denied.status_code == 401

    owner = rag_client.post(
        "/api/v1/auth/register",
        json={"email": "inbox-owner@example.com", "password": "password1"},
    )
    owner_headers = {"Authorization": f"Bearer {owner.json()['token']}"}
    created = rag_client.post(
        "/api/v1/repair/sessions",
        json={
            "title": "Owner only bug",
            "description": "calculate returns 1 instead of 2",
            "repository_path": str(repo),
            "provider": "mock",
        },
        headers=owner_headers,
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    other = rag_client.post(
        "/api/v1/auth/register",
        json={"email": "inbox-other@example.com", "password": "password1"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}
    hidden_list = rag_client.get("/api/v1/repair/sessions", headers=other_headers)
    assert hidden_list.status_code == 200
    assert all(item["id"] != session_id for item in hidden_list.json())
    hidden_get = rag_client.get(f"/api/v1/repair/sessions/{session_id}", headers=other_headers)
    assert hidden_get.status_code == 404

    visible = rag_client.get("/api/v1/repair/sessions", headers=owner_headers)
    assert visible.status_code == 200
    assert any(item["id"] == session_id for item in visible.json())

    rag_client.post("/api/v1/auth/logout", headers=owner_headers)
    after_logout = rag_client.get("/api/v1/repair/sessions", headers=owner_headers)
    assert after_logout.status_code == 401

    again = rag_client.post(
        "/api/v1/auth/login",
        json={"email": "inbox-owner@example.com", "password": "password1"},
    )
    restored = rag_client.get(
        "/api/v1/repair/sessions",
        headers={"Authorization": f"Bearer {again.json()['token']}"},
    )
    assert any(item["id"] == session_id for item in restored.json())


def test_provider_status_does_not_invent_reachability(rag_client: TestClient):
    status = rag_client.get("/api/v1/providers/status")
    assert status.status_code == 200
    body = status.json()
    assert "llm" in body
    assert "embeddings" in body
    assert "ready" in body
    assert "live generation call" in body["llm"]["note"] or "Mock" in body["llm"]["note"] or "missing" in body["llm"]["note"]
