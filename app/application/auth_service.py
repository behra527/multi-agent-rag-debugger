from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthorizationError, ValidationFailed
from app.core.passwords import hash_password, hash_token, verify_password
from app.db.models import SessionTokenRecord, UserRecord, utcnow

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Identity:
    workspace_id: str
    user_id: str | None = None
    email: str | None = None
    actor: str = "anonymous"
    auth_type: str = "anonymous"


def register_user(db: Session, email: str, password: str) -> tuple[UserRecord, str]:
    normalized = email.strip().lower()
    if not _EMAIL.match(normalized):
        raise ValidationFailed("A valid email address is required.")
    if len(password) < 8:
        raise ValidationFailed("Password must be at least 8 characters.")
    existing = db.query(UserRecord).filter(UserRecord.email == normalized).first()
    if existing:
        raise ValidationFailed("An account with this email already exists.")
    user = UserRecord(
        id=str(uuid4()),
        email=normalized,
        password_hash=hash_password(password),
        workspace_id=f"ws-{uuid4()}",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _issue_token(db, user)
    return user, token


def login_user(db: Session, email: str, password: str) -> tuple[UserRecord, str]:
    user = db.query(UserRecord).filter(UserRecord.email == email.strip().lower()).first()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthorizationError("Invalid email or password.")
    token = _issue_token(db, user)
    return user, token


def logout_user(db: Session, authorization: str | None) -> None:
    bearer = _bearer(authorization) if authorization else None
    if not bearer:
        return
    db.query(SessionTokenRecord).filter(SessionTokenRecord.token_hash == hash_token(bearer)).delete()
    db.commit()


def authenticate_request(
    db: Session,
    authorization: str | None,
    requested_workspace: str | None,
) -> Identity:
    bearer = _bearer(authorization)
    service_token = settings.api_auth_token.strip()
    if bearer and service_token and bearer == service_token:
        workspace = (requested_workspace or settings.default_workspace_id).strip()
        return Identity(
            workspace_id=workspace or settings.default_workspace_id,
            actor="service",
            auth_type="service_token",
        )

    if bearer:
        session = db.get(SessionTokenRecord, hash_token(bearer))
        expires = session.expires_at if session is not None else None
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if session is None or expires is None or expires < datetime.now(timezone.utc):
            raise AuthorizationError("Invalid or expired session token.")
        user = db.get(UserRecord, session.user_id)
        if user is None:
            raise AuthorizationError("Invalid session token.")
        if requested_workspace and requested_workspace != user.workspace_id:
            raise AuthorizationError("Workspace does not belong to this account.")
        return Identity(
            workspace_id=user.workspace_id,
            user_id=user.id,
            email=user.email,
            actor=user.email,
            auth_type="user",
        )

    if settings.auth_mode == "required":
        raise AuthorizationError("Authentication is required.")

    workspace = (requested_workspace or settings.default_workspace_id).strip()
    return Identity(workspace_id=workspace or settings.default_workspace_id)


def _issue_token(db: Session, user: UserRecord) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        SessionTokenRecord(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
        )
    )
    db.commit()
    return token


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise AuthorizationError("Authorization header must use Bearer scheme.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthorizationError("Missing bearer token.")
    return token
