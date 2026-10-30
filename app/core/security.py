"""Authentication, upload validation, and outbound URL controls."""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import AuthorizationError, ValidationFailed

ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".json"}
FORBIDDEN_FILENAME_CHARS = re.compile(r"[\\/:*?\"<>|\x00-\x1f]")


def require_auth(authorization: str | None) -> None:
    expected = settings.api_auth_token.strip()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthorizationError("Missing bearer token.")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise AuthorizationError("Invalid bearer token.")


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}:
        raise ValidationFailed("A valid filename is required.")
    if FORBIDDEN_FILENAME_CHARS.search(name):
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if not name:
        raise ValidationFailed("Filename is empty after sanitization.")
    return name[:180]


def validate_upload(filename: str, size: int, content_type: str | None = None) -> str:
    safe_name = sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationFailed(
            f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}",
            details={"filename": safe_name},
        )
    if size <= 0:
        raise ValidationFailed("Uploaded file is empty.")
    if size > settings.max_upload_bytes:
        raise ValidationFailed(
            f"File exceeds maximum size of {settings.max_upload_bytes} bytes.",
            details={"size": size},
        )
    if content_type and content_type.lower() in {
        "application/x-msdownload",
        "application/x-executable",
        "application/x-sh",
    }:
        raise ValidationFailed("Executable uploads are not allowed.")
    return safe_name


def is_safe_outbound_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
    if host in blocked_hosts or host.endswith(".internal"):
        return False
    try:
        address = ipaddress.ip_address(host)
        if address.is_private or address.is_loopback or address.is_link_local:
            return False
    except ValueError:
        pass
    return True


def assert_safe_provider_url(url: str) -> None:
    if settings.app_env == "development" and urlparse(url).hostname in {
        "localhost",
        "127.0.0.1",
    }:
        return
    if not is_safe_outbound_url(url):
        raise ValidationFailed(
            "Provider URL is not allowed (SSRF protection).",
            details={"url": url},
        )
