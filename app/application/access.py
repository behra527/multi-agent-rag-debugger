from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models import KnowledgeBaseRecord


def require_kb(db: Session, knowledge_base_id: str, workspace_id: str) -> KnowledgeBaseRecord:
    kb = db.get(KnowledgeBaseRecord, knowledge_base_id)
    if kb is None:
        raise NotFoundError(f"Knowledge base {knowledge_base_id} was not found.")
    if kb.workspace_id != workspace_id:
        raise ForbiddenError("Knowledge base belongs to another workspace.")
    return kb
