from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings


def collect_status(db: Session) -> dict:
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        database = f"unhealthy: {exc}"

    llm = {
        "provider": settings.llm_provider,
        "configured": True,
        "reachable": True,
        "note": "Status reflects configuration, not a live generation call.",
    }
    if settings.llm_provider == "openai":
        llm["configured"] = bool(settings.openai_api_key)
        llm["reachable"] = llm["configured"]
        if not llm["configured"]:
            llm["note"] = "OPENAI_API_KEY is missing."
    elif settings.llm_provider == "openrouter":
        llm["configured"] = bool(settings.openrouter_api_key)
        llm["reachable"] = llm["configured"]
        if not llm["configured"]:
            llm["note"] = "OPENROUTER_API_KEY is missing."
    elif settings.llm_provider == "ollama":
        llm["note"] = f"Ollama URL {settings.ollama_base_url} is configured; live ping is not performed by default."
    elif settings.llm_provider == "mock":
        llm["note"] = "Mock provider is local and deterministic."

    embeddings = {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "configured": True,
        "reachable": True,
        "note": "Status reflects configuration, not a live embed call.",
    }
    if settings.embedding_provider == "openai":
        embeddings["configured"] = bool(settings.openai_api_key)
        embeddings["reachable"] = embeddings["configured"]
        if not embeddings["configured"]:
            embeddings["note"] = "OPENAI_API_KEY is missing for OpenAI embeddings."
    elif settings.embedding_provider == "hash":
        embeddings["note"] = "Hash embeddings are deterministic and not semantic."
    elif settings.embedding_provider == "local":
        embeddings["note"] = "Local sentence-transformers will download weights on first use."

    return {
        "database": database,
        "llm": llm,
        "embeddings": embeddings,
        "auth_mode": settings.auth_mode,
        "job_execution_mode": settings.job_execution_mode,
        "reranker": settings.reranker,
        "ready": database == "ok" and llm["configured"] and embeddings["configured"],
    }
