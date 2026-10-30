from __future__ import annotations

from pathlib import Path

from app.core.config import settings

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "indexes",
    "uploads",
    "cloned",
}


def allowed_roots() -> list[Path]:
    raw = (settings.allowed_repo_roots or "").strip()
    if raw:
        return [Path(part).expanduser().resolve() for part in raw.split(",") if part.strip()]
    return [
        (settings.data_dir / "demos").resolve(),
        (settings.data_dir / "sample_project").resolve(),
        (settings.data_dir / "cloned").resolve(),
    ]


def is_allowed_path(path: Path) -> bool:
    if not (settings.allowed_repo_roots or "").strip() and settings.app_env != "production":
        return True
    resolved = path.expanduser().resolve()
    for root in allowed_roots():
        try:
            if resolved == root or resolved.is_relative_to(root):
                return True
        except ValueError:
            continue
    return False


def _demo_description(folder: Path) -> str:
    bug = folder / "BUG_REPORT.md"
    readme = folder / "README.md"
    source = bug if bug.exists() else readme
    if not source.exists():
        return ""
    try:
        for line in source.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                return text[:180]
    except OSError:
        return ""
    return ""


def list_authorized_repositories() -> list[dict[str, str]]:
    """List demo projects and other authorized local folders the API can read."""
    found: dict[str, dict[str, str]] = {}
    demos = (settings.data_dir / "demos").resolve()
    if demos.is_dir():
        for child in sorted(demos.iterdir()):
            if not child.is_dir() or child.name.startswith(".") or child.name in SKIP_DIR_NAMES:
                continue
            found[str(child.resolve())] = {
                "name": child.name,
                "path": str(child.resolve()),
                "kind": "demo",
                "description": _demo_description(child),
            }

    sample = (settings.data_dir / "sample_project").resolve()
    if sample.is_dir():
        found[str(sample)] = {
            "name": sample.name,
            "path": str(sample),
            "kind": "demo",
            "description": _demo_description(sample),
        }

    raw = (settings.allowed_repo_roots or "").strip()
    if raw:
        for root in allowed_roots():
            if not root.exists() or not root.is_dir():
                continue
            key = str(root)
            if key not in found:
                found[key] = {
                    "name": root.name,
                    "path": key,
                    "kind": "git" if (root / ".git").exists() else "local",
                    "description": "",
                }
    return list(found.values())[:80]
