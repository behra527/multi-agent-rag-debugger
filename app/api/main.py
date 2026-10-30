from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.error_handlers import register_error_handlers
from app.api.middleware import RateLimitMiddleware, RequestIdMiddleware
from app.api.v1.rag_routes import router as rag_router
from app.api.v1.repair_routes import router as repair_router
from app.api.v1.router import router as api_v1_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.models import IssueRequest
from app.core.report import FinalDebuggingReport
from app.db.database import init_db
from app.factory import create_project_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize logging, storage directories, and database schemas."""
    configure_logging(settings.log_level)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    from app.application.jobs import recover_interrupted_jobs
    from app.core.logging import get_logger
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        recovered = recover_interrupted_jobs(session)
        if recovered:
            get_logger("startup").warning("Marked %s interrupted jobs as failed.", recovered)
        if settings.app_env == "production" and settings.auth_mode != "required":
            get_logger("startup").warning(
                "AUTH_MODE is optional while APP_ENV=production. Set AUTH_MODE=required for shared deployments."
            )
    finally:
        session.close()
    yield


app = FastAPI(
    title="Multi-Agent RAG Debugger",
    description=(
        "Investigate, diagnose, and evaluate RAG pipelines using user-provided "
        "documents, hybrid retrieval, multi-agent analysis, and persisted experiments. "
        "A legacy code-debugging lab remains available under the original /api/v1 debugging-runs routes."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)
register_error_handlers(app)

app.include_router(api_v1_router)
app.include_router(rag_router)
app.include_router(repair_router)


# Legacy endpoints for backward compatibility
class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/health", response_model=HealthResponse, tags=["legacy"])
def health() -> HealthResponse:
    """Legacy health check endpoint."""
    return HealthResponse(
        status="ok",
        service="multi-agent-rag-debugger",
    )


@app.post("/debug", response_model=FinalDebuggingReport, tags=["legacy"])
def debug_issue(issue: IssueRequest) -> FinalDebuggingReport:
    """Legacy debugging endpoint."""
    repository = Path(issue.repository_path).expanduser().resolve()

    if not repository.exists():
        raise HTTPException(
            status_code=400,
            detail="Repository path does not exist.",
        )

    if not repository.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Repository path must be a directory.",
        )

    normalized_issue = issue.model_copy(
        update={"repository_path": str(repository)}
    )

    try:
        manager = create_project_manager()
        return manager.handle_issue(normalized_issue)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
