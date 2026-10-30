from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from app.rag.ingestion import extract_text, normalize_text
from tests.pdf_builder import build_simple_pdf


def test_extract_pdf_text():
    payload = build_simple_pdf("Refunds are issued within 14 days.")
    text = extract_text(Path("policy.pdf"), payload)
    assert "Refunds" in text
    assert "14 days" in text


def test_extract_docx_text():
    document = Document()
    document.add_paragraph("Shipping is available worldwide except restricted destinations.")
    buffer = BytesIO()
    document.save(buffer)
    text = normalize_text(extract_text(Path("shipping.docx"), buffer.getvalue()))
    assert "Shipping is available worldwide" in text


def test_upload_pdf_and_docx_through_api(rag_client: TestClient):
    kb = rag_client.post(
        "/api/v1/knowledge-bases",
        json={"name": "office-docs", "embedding_provider": "hash"},
    ).json()
    pdf = rag_client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("policy.pdf", build_simple_pdf("Refunds are issued within 14 days."), "application/pdf")},
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.json()["status"] == "indexed"

    document = Document()
    document.add_paragraph("Office hours are Monday through Friday.")
    buffer = BytesIO()
    document.save(buffer)
    docx = rag_client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={
            "file": (
                "hours.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert docx.status_code == 200, docx.text
    assert docx.json()["status"] == "indexed"

    query = rag_client.post(
        "/api/v1/rag/query",
        json={
            "knowledge_base_id": kb["id"],
            "query": "When are refunds issued?",
            "config": {"generate_answer": False, "retrieval_mode": "lexical"},
        },
    )
    assert query.status_code == 200, query.text
    sources = [item["chunk"]["source"] for item in query.json()["retrieved"]]
    assert "policy.pdf" in sources
