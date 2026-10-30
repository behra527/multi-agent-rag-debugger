from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Multi-Agent RAG Debugger"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    openrouter_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)

    llm_provider: str = Field(default="mock")
    llm_model: str = "openai/gpt-4o-mini"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1200, gt=0)
    llm_timeout_seconds: float = Field(default=45.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=6)

    embedding_provider: str = Field(default="local")
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = Field(default=384, gt=0)

    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{BASE_DIR / 'data' / 'debugger.db'}"
    )

    sandbox_timeout_seconds: int = 120
    sandbox_max_attempts: int = 2

    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://localhost:8000",
        ]
    )

    api_auth_token: str = Field(default="", repr=False)
    auth_mode: str = Field(default="optional")
    default_workspace_id: str = "default"
    session_ttl_hours: int = Field(default=168, gt=0)
    reranker: str = Field(default="lexical")

    max_upload_bytes: int = Field(default=15 * 1024 * 1024, gt=0)
    max_documents_per_kb: int = Field(default=200, gt=0)
    max_chunks_per_document: int = Field(default=4000, gt=0)
    max_context_chars: int = Field(default=12000, gt=0)
    max_llm_calls_per_workflow: int = Field(default=12, gt=0)
    max_workflow_seconds: int = Field(default=180, gt=0)
    max_parallel_agents: int = Field(default=3, gt=0)
    default_chunk_size: int = Field(default=800, gt=0)
    default_chunk_overlap: int = Field(default=120, ge=0)
    default_top_k: int = Field(default=5, gt=0, le=50)

    usd_per_1k_prompt_tokens: float = Field(default=0.00015, ge=0)
    usd_per_1k_completion_tokens: float = Field(default=0.0006, ge=0)

    github_token: str = Field(default="", repr=False)
    allowed_repo_roots: str = ""
    github_clone_dir: Path = BASE_DIR / "data" / "cloned"

    job_execution_mode: str = Field(default="inline")
    rate_limit_per_minute: int = Field(default=0, ge=0)
    max_evaluation_items: int = Field(default=200, gt=0)

    project_root: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    prompts_dir: Path = BASE_DIR / "prompts"
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    index_dir: Path = BASE_DIR / "data" / "indexes"

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        allowed = {"openai", "openrouter", "ollama", "mock"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"llm_provider must be one of {sorted(allowed)}")
        return normalized

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        allowed = {"local", "hash", "openai"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"embedding_provider must be one of {sorted(allowed)}")
        return normalized

    @field_validator("job_execution_mode")
    @classmethod
    def validate_job_mode(cls, value: str) -> str:
        allowed = {"inline", "background"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"job_execution_mode must be one of {sorted(allowed)}")
        return normalized

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        allowed = {"optional", "required"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"auth_mode must be one of {sorted(allowed)}")
        return normalized

    @field_validator("reranker")
    @classmethod
    def validate_reranker(cls, value: str) -> str:
        allowed = {"lexical", "cross_encoder"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"reranker must be one of {sorted(allowed)}")
        return normalized

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("ollama_base_url must be an http(s) URL")
        return value.rstrip("/")


settings = Settings()
