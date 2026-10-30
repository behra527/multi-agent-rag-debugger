import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def require_app_token() -> str:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.example")
    token = os.environ.get("API_TOKEN")
    if not token:
        raise RuntimeError("APP_TOKEN is not set")
    return token
