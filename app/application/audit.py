from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import AuditLogRecord


def record(
    db: Session,
    *,
    workspace_id: str,
    action: str,
    actor: str = "anonymous",
    resource_type: str = "",
    resource_id: str = "",
    message: str = "",
) -> None:
    db.add(
        AuditLogRecord(
            id=str(uuid4()),
            workspace_id=workspace_id,
            actor=actor[:255],
            action=action[:64],
            resource_type=resource_type[:64],
            resource_id=resource_id[:64],
            message=message[:4000],
        )
    )
    db.commit()


def list_events(db: Session, workspace_id: str, limit: int = 50) -> list[AuditLogRecord]:
    return (
        db.query(AuditLogRecord)
        .filter(AuditLogRecord.workspace_id == workspace_id)
        .order_by(AuditLogRecord.created_at.desc())
        .limit(limit)
        .all()
    )
