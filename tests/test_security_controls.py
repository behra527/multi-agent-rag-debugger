import pytest

from app.core.exceptions import AuthorizationError, ValidationFailed
from app.core.security import is_safe_outbound_url, require_auth, validate_upload


def test_validate_upload_rejects_executables_and_empty_files():
    with pytest.raises(ValidationFailed):
        validate_upload("malware.exe", 12)
    with pytest.raises(ValidationFailed):
        validate_upload("notes.txt", 0)
    assert validate_upload("notes.txt", 12) == "notes.txt"


def test_require_auth_when_token_configured(monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "api_auth_token", "secret-token")
    with pytest.raises(AuthorizationError):
        require_auth(None)
    with pytest.raises(AuthorizationError):
        require_auth("Bearer wrong")
    require_auth("Bearer secret-token")


def test_ssrf_blocks_private_hosts():
    assert is_safe_outbound_url("http://127.0.0.1/v1") is False
    assert is_safe_outbound_url("http://169.254.169.254/latest") is False
    assert is_safe_outbound_url("https://api.openai.com/v1") is True
