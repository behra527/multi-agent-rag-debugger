from pathlib import Path

from pydantic import Field
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

    openrouter_api_key: str = Field(default="", repr=False)

    llm_model: str = "openai/gpt-oss-20b"
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=500, gt=0)

    project_root: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    prompts_dir: Path = BASE_DIR / "prompts"


settings = Settings()