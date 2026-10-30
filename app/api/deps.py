from contextvars import ContextVar

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.application.auth_service import Identity, authenticate_request
from app.core.exceptions import AuthorizationError
from app.db.database import get_db

current_identity: ContextVar[Identity | None] = ContextVar("current_identity", default=None)


def get_identity(
    authorization: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Identity:
    identity = authenticate_request(db, authorization, x_workspace_id)
    current_identity.set(identity)
    return identity


def get_workspace(identity: Identity = Depends(get_identity)) -> str:
    return identity.workspace_id


def require_user(identity: Identity = Depends(get_identity)) -> Identity:
    if identity.auth_type != "user" or not identity.user_id:
        raise AuthorizationError("Sign in to access your repair inbox.")
    return identity
